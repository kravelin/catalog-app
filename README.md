# Catalog App Project

This system runs on localhost port 8000 and uses Flask and SQLAlchemy on Python 2.7. See requirements.txt for the modules that need to be installed.

Once the requirements are installed run 'python database_setup.py' to initialize the database if you don't want to use the one included.

You can then run the app using 'python project.py'. This will start the server running. You can conect to the app using your web browser and going to http://localhost:8000.

No changes can be made to the database unless a user logs in using Google (just click on 'login' in the upper right corner). Very basic information is all this app checks for: username, email, profile picture.

Once logged in a user can add, edit, or delete their own categories and items. Users cannot edit or delete a category or item belonging to another user.

In both cases below the add/edit forms will discard any other file type that's uploaded.
* Categories can have a banner image and it should be 1024x150 and in jpg, gif, png, or svg format.
* Items can have an image and it should be 150x150 and in jpg, gif, png, or svg format.

You can get JSON outputs for the categories, items, or a specific item by using the following urls (note that images will only be filenames not the actual images):
* categories: http://localhost:8000/catalog/JSON
* items in a category: http://localhost:8000/catalog/\<category_id\>/items/JSON
* a specific item: http://localhost:8000/catalog/\<category_id\>/item/\<item_id\>/JSON

NOTE: If a user deletes one of their categories all items under that category will also be deleted no matter who created them. This prevents orphan items from floating around in the database.
