from flask import Flask, render_template, request, redirect, jsonify, url_for
from sqlalchemy import create_engine, asc, desc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Category, Item, User
from flask import session as login_session
from catalog_helper import store_image, remove_image
from catalog_helper import createUser, getUserInfo, getUserID
from catalog_helper import getCatalog, getCategory, getItems, getItem
from catalog_helper import getCatalog_ASC, getLatestItems, addCategory
from catalog_helper import addItem, updateCategory, updateItem
from catalog_helper import removeCategory, removeItem
import random
import string
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response, flash
import requests
from flask_bootstrap import Bootstrap
from flask.ext.seasurf import SeaSurf
from werkzeug.utils import secure_filename
from functools import wraps
import os

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(APP_ROOT, 'static/uploads')

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
Bootstrap(app)
csrf = SeaSurf(app)

CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Item Catalog Project"


# User login check wrapper
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in login_session:
            return redirect(url_for('showLogin'))
        return f(*args, **kwargs)
    return decorated_function


# Create anti-forgery state token
@app.route('/login/')
def showLogin():
    if 'state' not in login_session:
        state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                        for x in xrange(32))
        login_session['state'] = state
    else:
        state = login_session['state']
    return render_template('login.html', STATE=state)


@csrf.exempt
@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_credentials = login_session.get('credentials')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_credentials is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('Current user is already connected.'),
                                 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']
    # ADD PROVIDER TO LOGIN SESSION
    login_session['provider'] = 'google'

    # see if user exists, if it doesn't make a new one
    user_id = getUserID(data["email"])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: 150px;' \
              ' -webkit-border-radius: 150px;-moz-border-radius: 150px;"> '
    flash("you are now logged in as %s" % login_session['username'])
    print "done!"
    return output


# DISCONNECT - Revoke a current user's token and reset their login_session
@app.route('/gdisconnect')
def gdisconnect():
    # Only disconnect a connected user.
    access_token = login_session.get('access_token')
    if access_token is None:
        response = make_response(
            json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    if result['status'] != '200':
        # For whatever reason, the given token was invalid.
        response = make_response(
            json.dumps('Failed to revoke token for given user.'), 400)
        response.headers['Content-Type'] = 'application/json'
        return response


# Disconnect based on provider
@app.route('/disconnect')
def disconnect():
    if 'provider' in login_session:
        if login_session['provider'] == 'google':
            gdisconnect()
            del login_session['gplus_id']
            del login_session['access_token']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        del login_session['user_id']
        del login_session['provider']
        del login_session['state']
        flash("You have successfully been logged out.")
        return redirect(url_for('showCatalog'))
    else:
        flash("You were not logged in")
        return redirect(url_for('showCatalog'))


# JSON APIs to view Catalog Information
@app.route('/catalog/JSON')
def catalogJSON():
    categories = getCatalog();
    return jsonify(Categories=[c.serialize for c in categories])


@app.route('/catalog/<int:category_id>/items/JSON')
def categoryItemsJSON(category_id):
    items = getItems(category_id)
    return jsonify(Items=[i.serialize for i in items])


@app.route('/catalog/<int:category_id>/item/<int:item_id>/JSON')
def itemJSON(category_id, item_id):
    Item = getItem(item_id)
    return jsonify(Item=Item.serialize)


# Show all categories
@app.route('/')
@app.route('/catalog/')
def showCatalog():
    categories = getCatalog_ASC("name")
    items = getLatestItems()
    if 'username' not in login_session:
        return render_template('publicCatalog.html', categories=categories,
                               items = items)
    else:
        return render_template('catalog.html', categories=categories,
                               items = items)


# Create a new category
@app.route('/category/new/', methods=['GET', 'POST'])
@login_required
def newCategory():
    if request.method == 'POST':
        if 'banner' in request.files:
            banner = store_image(request.files['banner'])
        else:
            banner = ''

        addCategory(request.form['name'], login_session['user_id'], banner)
        flash('New Category, %s, Successfully Created' % request.form['name'])
        return redirect(url_for('showCatalog'))
    else:
        return render_template('newCategory.html')


# Edit a category
@app.route('/category/<int:category_id>/edit/', methods=['GET', 'POST'])
@login_required
def editCategory(category_id):
    editedCategory = getCategory(category_id)
    if editedCategory.user_id != login_session['user_id']:
        return "<script>function myFunction() {alert('You are not authorized" \
               " to edit this category. Please create your own category in " \
               " order to edit.');}</script><body onload='myFunction()''>"
    if request.method == 'POST':
        if request.form['name']:
            oldName = editedCategory.name
            editedCategory.name = request.form['name']
            flash('Category Successfully Renamed From %s To %s' %
                  (oldName, editedCategory.name))
        if 'banner' in request.files:
            if editedCategory.banner != '':
                remove_image(editedCategory.banner)
            editedCategory.banner = store_image(request.files['banner'])
            flash('Category Banner Image Successfully Updated')
        updateCategory(editedCategory)
        return redirect(url_for('showCatalog'))
    else:
        return render_template('editCategory.html', category=editedCategory)


# Delete a category
@app.route('/category/<int:category_id>/delete/', methods=['GET', 'POST'])
@login_required
def deleteCategory(category_id):
    category = getCategory(category_id)
    if category.user_id != login_session['user_id']:
        return "<script>function myFunction() {alert('You are not authorized" \
              " to delete this category. Please create your own category in " \
              "order to delete.');}</script><body onload='myFunction()''>"
    if request.method == 'POST':
        removeCategory(category_id)
        flash('%s Successfully Deleted' % category.name)
        return redirect(url_for('showCatalog'))
    else:
        return render_template('deleteCategory.html', category = category)


# Show a list of items in a category
@app.route('/category/<int:category_id>/')
@app.route('/category/<int:category_id>/items/')
def showCategory(category_id):
    category = getCategory(category_id)
    creator = getUserInfo(category.user_id)
    items = getItems(category_id)
    if 'username' not in login_session:
        return render_template('publicCategory.html', items = items,
                               category = category, creator = creator)
    else:
        return render_template('category.html', items = items,
                               category = category, creator = creator)


# Show the details of an item
@app.route('/category/<int:category_id>/item/<int:item_id>')
def showItem(category_id, item_id):
    category = getCategory(category_id)
    item = getItem(item_id)
    creator = getUserInfo(item.user_id)
    if 'username' not in login_session:
        return render_template('publicItem.html', item = item,
                               category = category, creator = creator)
    else:
        return render_template('item.html', item = item,
                               category = category, creator = creator)


# Create a new item in a category
@app.route('/category/<int:category_id>/item/new/', methods=['GET', 'POST'])
@login_required
def newItem(category_id):
    category = getCategory(category_id)
    if request.method == 'POST':
        if 'image' in request.files:
            image = store_image(request.files['image'])
        else:
            image = ''

        addItem(request.form['name'],
                request.form['description'],
                request.form['cost'],
                request.form['weight'],
                image,
                category_id,
                login_session['user_id'])

        flash('New Item, %s, In Category, %s, Successfully Created' % (request.form['name'], category.name))
        return redirect(url_for('showCategory', category_id = category_id))
    else:
        return render_template('newItem.html', category = category)


# Edit an item
@app.route('/category/<int:category_id>/item/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def editItem(category_id, item_id):
    editedItem = getItem(item_id)
    if login_session['user_id'] != editedItem.user_id:
        return "<script>function myFunction() {alert('You are not authorized" \
               " to edit this item. Please create your own item in order to " \
               "edit it.');}</script><body onload='myFunction()''>"
    if request.method == 'POST':
        oldName = None
        if request.form['name']:
            oldName = editedItem.name
            editedItem.name = request.form['name']
        if request.form['description']:
            editedItem.description = request.form['description']
        if request.form['cost']:
            editedItem.cost = request.form['cost']
        if request.form['weight']:
            editedItem.weight = request.form['weight']
        if 'image' in request.files:
            if editedItem.image != '':
                remove_image(editedItem.image)
            editedItem.image = store_image(request.files['image'])
        updateItem(editedItem)
        if oldName:
            flash('Item, %s, Renamed To, %s, and Successfully Edited' %
                  (oldName, editedItem.name))
        else:
            flash('Item %s Successfully Edited' % editedItem.name)
        return redirect(url_for('showCategory', category_id=category_id))
    else:
        return render_template('editItem.html', category_id=category_id,
                               item_id=item_id, item=editedItem)


# Delete an item
@app.route('/category/<int:category_id>/item/<int:item_id>/delete', methods=['GET', 'POST'])
@login_required
def deleteItem(category_id, item_id):
    itemToDelete = getItem(item_id)
    if login_session['user_id'] != itemToDelete.user_id:
        return "<script>function myFunction() {alert('You are not authorized" \
        " to delete this item. Please create your own item in order to " \
        "delete it.');}</script><body onload='myFunction()''>"
    if request.method == 'POST':
        removeItem(itemToDelete)
        flash('Item, %s, Successfully Deleted' % itemToDelete.name)
        return redirect(url_for('showCategory', category_id=category_id))
    else:
        return render_template('deleteItem.html', item=itemToDelete)


if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.run(host='0.0.0.0', port=8000)
