from flask import Flask, render_template, request, redirect, jsonify, url_for, flash
from sqlalchemy import create_engine, asc, desc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Category, Item, User
from flask import session as login_session
import random
import string
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests
from flask_bootstrap import Bootstrap
from werkzeug.utils import secure_filename
import os

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(APP_ROOT, 'static/uploads')
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'gif', 'svg', 'jpeg'])

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
Bootstrap(app)

CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Item Catalog Project"


# Connect to Database and create database session
engine = create_engine('sqlite:///equipment.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


# Image upload functions
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def store_image(rawfile):
    if rawfile.filename == '':
        return ''
        flash("upload image had no filename")
    if rawfile and allowed_file(rawfile.filename):
        filename = secure_filename(rawfile.filename)
        rawfile.save(os.path.join( UPLOAD_FOLDER, filename))
        flash("image file saved as %s" % filename)
        return filename
    else:
        flash("Uploaded image was not a valid file format so was not saved.")
        flash("File was named: %s" % rawfile.filename)
        return ''


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


# User Helper Functions
def createUser(login_session):
    newUser = User(name=login_session['username'], email=login_session[
                   'email'], picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


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
@app.route('/catalog/<int:category_id>/items/JSON')
def categoryItemsJSON(category_id):
    catalog = session.query(Category).filter_by(id=category_id).one()
    items = session.query(Item).filter_by(
        category_id=category_id).all()
    return jsonify(Items=[i.serialize for i in items])


@app.route('/catalog/<int:category_id>/items/<int:item_id>/JSON')
def itemJSON(category_id, item_id):
    Item = session.query(Item).filter_by(id=item_id).one()
    return jsonify(Item=Item.serialize)


@app.route('/catalog/JSON')
def catalogJSON():
    categories = session.query(Category).all()
    return jsonify(Categories=[c.serialize for c in categories])


# Show all categories
@app.route('/')
@app.route('/catalog/')
def showCatalog():
    categories = session.query(Category).join(User).order_by(asc(Category.name))
    items = session.query(Item).order_by(desc(Item.id)).limit(10)
    if 'username' not in login_session:
        return render_template('publicCatalog.html', categories=categories,
                               items = items)
    else:
        return render_template('catalog.html', categories=categories,
                               items = items)


# Create a new category
@app.route('/category/new/', methods=['GET', 'POST'])
def newCategory():
    if 'username' not in login_session:
        return redirect('/login')
    if request.method == 'POST':
        if 'banner' in request.files:
            banner = store_image(request.files['banner'])
        else:
            banner = ''

        newCategory = Category(
            name = request.form['name'],
            user_id = login_session['user_id'],
            banner = banner)
        session.add(newCategory)
        flash('New Category, %s, Successfully Created' % newCategory.name)
        session.commit()
        return redirect(url_for('showCatalog'))
    else:
        return render_template('newCategory.html')


# Edit a category
@app.route('/category/<int:category_id>/edit/', methods=['GET', 'POST'])
def editCategory(category_id):
    editedCategory = session.query(Category).filter_by(id=category_id).one()
    if 'username' not in login_session:
        return redirect('/login')
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
            editedCategory.banner = store_image(request.files['banner'])
            flash('Category Banner Image Successfully Updated')
        session.add(editedCategory)
        session.commit()
        return redirect(url_for('showCatalog'))
    else:
        return render_template('editCategory.html', category=editedCategory)


# Delete a category
@app.route('/category/<int:category_id>/delete/', methods=['GET', 'POST'])
def deleteCategory(category_id):
    category = session.query(Category).filter_by(id=category_id).one()
    if 'username' not in login_session:
        return redirect('/login')
    if category.user_id != login_session['user_id']:
        return "<script>function myFunction() {alert('You are not authorized" \
              " to delete this category. Please create your own category in " \
              "order to delete.');}</script><body onload='myFunction()''>"
    if request.method == 'POST':
        session.delete(category)
        flash('%s Successfully Deleted' % category.name)
        session.commit()
        return redirect(url_for('showCatalog', category_id = category_id))
    else:
        return render_template('deleteCategory.html', category = category)


# Show a list of items in a category
@app.route('/category/<int:category_id>/')
@app.route('/category/<int:category_id>/items/')
def showCategory(category_id):
    category = session.query(Category).filter_by(id = category_id).one()
    creator = getUserInfo(category.user_id)
    items = session.query(Item).filter_by(category_id=category_id).all()
    if 'username' not in login_session:
        return render_template('publicCategory.html', items = items,
                               category = category, creator = creator)
    else:
        return render_template('category.html', items = items,
                               category = category, creator = creator)


# Show the details of an item
@app.route('/category/<int:category_id>/item/<int:item_id>')
def showItem(category_id, item_id):
    category = session.query(Category).filter_by(id = category_id).one()
    item = session.query(Item).filter_by(id = item_id).one()
    creator = getUserInfo(item.user_id)
    if 'username' not in login_session:
        return render_template('publicItem.html', item = item,
                               category = category, creator = creator)
    else:
        return render_template('item.html', item = item,
                               category = category, creator = creator)


# Create a new item in a category
@app.route('/category/<int:category_id>/item/new/', methods=['GET', 'POST'])
def newItem(category_id):
    if 'username' not in login_session:
        return redirect('/login')
    category = session.query(Category).filter_by(id=category_id).one()
    if request.method == 'POST':
        if 'image' in request.files:
            image = store_image(request.files['image'])
        else:
            image = ''

        newItem = Item(name = request.form['name'],
                       description = request.form['description'],
                       cost = request.form['cost'],
                       weight = request.form['weight'],
                       image = image,
                       category_id = category_id,
                       user_id = login_session['user_id'])
        session.add(newItem)
        session.commit()
        flash('New Item, %s, In Category, %s, Successfully Created' % (newItem.name, category.name))
        return redirect(url_for('showCategory', category_id = category_id))
    else:
        return render_template('newItem.html', category = category)


# Edit an item
@app.route('/category/<int:category_id>/item/<int:item_id>/edit', methods=['GET', 'POST'])
def editItem(category_id, item_id):
    if 'username' not in login_session:
        return redirect('/login')
    editedItem = session.query(Item).filter_by(id=item_id).one()
    category = session.query(Category).filter_by(id=category_id).one()
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
            editedItem.image = store_image(request.files['image'])
        session.add(editedItem)
        session.commit()
        if oldName:
            flash('Item, %s, Renamed To, %s, and Successfully Edited' %
                  (oldName, editedName.name))
        else:
            flash('Item %s Successfully Edited' % editedItem.name)
        return redirect(url_for('showCategory', category_id=category_id))
    else:
        return render_template('editItem.html', category_id=category_id,
                               item_id=item_id, item=editedItem)


# Delete an item
@app.route('/category/<int:category_id>/item/<int:item_id>/delete', methods=['GET', 'POST'])
def deleteItem(category_id, item_id):
    if 'username' not in login_session:
        return redirect('/login')
    category = session.query(Category).filter_by(id=category_id).one()
    itemToDelete = session.query(Item).filter_by(id=item_id).one()
    if login_session['user_id'] != item.user_id:
        return "<script>function myFunction() {alert('You are not authorized" \
        " to delete this item. Please create your own item in order to " \
        "delete it.');}</script><body onload='myFunction()''>"
    if request.method == 'POST':
        session.delete(itemToDelete)
        session.commit()
        flash('Item, %s, Successfully Deleted' % itemToDelete.name)
        return redirect(url_for('showCategory', category_id=category_id))
    else:
        return render_template('deleteItem.html', item=itemToDelete)


if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.run(host='0.0.0.0', port=8000)
