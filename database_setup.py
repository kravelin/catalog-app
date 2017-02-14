from sqlalchemy import Column, ForeignKey, Integer, String, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref
from sqlalchemy import create_engine

Base = declarative_base()


class User(Base):
    __tablename__ = 'user'


    name = Column(String(80), nullable = False)
    id = Column(Integer, primary_key = True)
    email = Column(String(250))
    picture = Column(String(250))


class Category(Base):
    __tablename__ = 'category'

    id = Column(Integer, primary_key=True)
    name = Column(String(250), nullable=False)
    banner = Column(String(250))
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship("User")
    items = relationship("Item", cascade="all, delete-orphan")

    @property
    def serialize(self):
       """Return object data in easily serializeable format"""
       return {
           'name'         : self.name,
           'id'           : self.id,
           'user_id'      : self.user_id,
           'banner'       : self.banner
       }


class Item(Base):
    __tablename__ = 'item'


    name =Column(String(80), nullable = False)
    id = Column(Integer, primary_key = True)
    description = Column(String(250))
    cost = Column(String(10))
    weight = Column(String(10))
    image = Column(String(250))
    category_id = Column(Integer,ForeignKey('category.id'))
    user_id = Column(Integer,ForeignKey('user.id'))
    category = relationship("Category")
    user = relationship("User")


    @property
    def serialize(self):
       """Return object data in easily serializeable format"""
       return {
           'name'         : self.name,
           'description'  : self.description,
           'cost'         : self.cost,
           'weight'       : self.weight,
           'image'        : self.image,
           'id'           : self.id,
           'user_id'      : self.user_id,
           'category_id'  : self.category_id
       }


engine = create_engine('sqlite:///equipment.db')


Base.metadata.create_all(engine)
