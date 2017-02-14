import os
import requests
from werkzeug.utils import secure_filename
from sqlalchemy import create_engine, asc, desc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Category, Item, User
from flask import flash, jsonify
import json


APP_ROOT = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(APP_ROOT, 'static/uploads')
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'gif', 'svg', 'jpeg'])


# Connect to Database and create database session
engine = create_engine('sqlite:///equipment.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


# Image upload and removal functions
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def store_image(rawfile):
    if rawfile.filename == '':
        flash("upload image had no filename")
        return ''
    if rawfile and allowed_file(rawfile.filename):
        filename = secure_filename(rawfile.filename)
        existingfiles = next(os.walk(UPLOAD_FOLDER))[2]
        for file in existingfiles:
            if filename == file:
                flash("a file with that name already exists, image not saved")
                return ''
        rawfile.save(os.path.join( UPLOAD_FOLDER, filename))
        flash("image file saved as %s" % filename)
        return filename
    else:
        flash("Uploaded image was not a valid file format so was not saved.")
        flash("File was named: %s" % rawfile.filename)
        return ''


def remove_image(file):
    path = UPLOAD_FOLDER + '/' + file
    os.remove(path)


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


# database query functions
def getCatalog():
    return session.query(Category).all()


def getCatalog_ASC(field):
    field = "Category." + field
    return session.query(Category).order_by(asc(field))


def getCategory(category_id):
    return session.query(Category).filter_by(id = category_id).one()


def getItems(category_id):
    return session.query(Item).filter_by(category_id = category_id).all()


def getLatestItems():
    return session.query(Item).order_by(desc(Item.id)).limit(10)


def getItem(item_id):
    return session.query(Item).filter_by(id=item_id).one()


def addCategory(name, user_id, banner):
    newCategory = Category( name = name, user_id = user_id, banner = banner)
    session.add(newCategory)
    session.commit()


def updateCategory(category):
    session.add(category)
    session.commit()


def removeCategory(category_id):
    category = getCategory(category_id)
    banner = session.query(Category.banner).filter_by(id = category_id).scalar()
    remove_image(banner)
    items = getItems(category_id)
    for item in items:
        if item.image != '':
            remove_image(item.image)
    session.delete(category)
    session.commit()


def addItem(name, description, cost, weight, image, category_id, user_id):
    newItem = Item(name = name,
                   description = description,
                   cost = cost,
                   weight = weight,
                   image = image,
                   category_id = category_id,
                   user_id = user_id)
    session.add(newItem)
    session.commit()


def updateItem(item):
    session.add(item)
    session.commit()


def removeItem(item_id):
    item = getItem(item_id)
    remove_image(item.image)
    session.delete(item)
    session.commit()
