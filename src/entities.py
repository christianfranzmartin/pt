import uuid
import pandas as pd
import numpy as np
from src.io import IOController

class Entity:
    """
    Entities are the most abstract objects with some sort of data base representation
    """

    TYPE = 'abstract'
    REQUIRED_ARGS = []
    ALLOWED_TYPES = [str, int, float, np.float64]

    def __init__(self, store=True, **kwargs):
        """
        Initiates the entity
        :param kwargs: arguments
        """

        # check the attributes
        self._check_args(**kwargs)
        self._check_required_args(**kwargs)

        # add the attributes
        self._attrs = kwargs

        # all entities have an id
        if not 'id' in self._attrs.keys():
            id = str(uuid.uuid4())
            self._attrs.update({'id': id})
            if store:
                self.store()

    def update_attributes(self, **kwargs):
        """
        Updates arbitrary attributes passed as keyword arguments
        :param kwargs: keyword arguments
        :return: None
        """

        self._check_args(**kwargs)

        # udpate arguments
        self._attrs.update(kwargs)

        # save the attributes in the server
        self.update_in_store()

    @property
    def type(self):
        return self.TYPE

    @property
    def id(self):
        return self._attrs['id']

    @property
    def attrs(self):
        return self._attrs.copy()

    def to_df(self):
        dct = {attr: [self._attrs[attr]] for attr in self._attrs.keys()}
        return pd.DataFrame(dct)

    def _check_required_args(self, **kwargs):
        """
        Checks whether all required arguments were received
        :param kwargs: arguments
        :return: None
        """

        for arg in self.REQUIRED_ARGS:
            if arg not in kwargs.keys():
                raise ValueError('Required argument {} not provided'.format(arg))

    def _check_args(self, **kwargs):
        """
        Checks whether the arguments are in the required structure
        :param kwargs: arguments
        :return: None
        """

        for arg in kwargs.keys():
            if type(kwargs[arg]) not in self.ALLOWED_TYPES:
                raise TypeError('Argument {} has invalid type {}'.format(arg, type(kwargs[arg])))

    def store(self):
        IOController().store(self)

    def update_in_store(self):
        IOController().update(self)

    @classmethod
    def from_store(cls, id):
        dct = IOController().retrieve_by_id(cls.TYPE, id)
        return cls(**dct)


class NamedEntity(Entity):
    REQUIRED_ARGS = ['name']

    def __init__(self, store=True, **kwargs):
        super().__init__(store=False, **kwargs)

        if store:
            self.store()

    @property
    def name(self):
        return self._attrs['name']


class RelationalEntity(Entity):
    """
    Entities that can be in a one-to-many relationship with other entities
    """

    RELATIONSHIP_ATTR = 'relationships'
    REQUIRED_ARGS = ['name']

    def __init__(self, store=True, **kwargs):
        super().__init__(store=False, **kwargs)

        # init the relationship
        self._relationship_list = []
        relationship = kwargs.get(self.RELATIONSHIP_ATTR, None)
        self._add(relationship)

        # update in the attributes as well
        self._attrs.update({self.RELATIONSHIP_ATTR: self._relationship_list})

        if store:
            self.store()

    def _add(self, relationship):

        # entities relationships are stored with ids
        # we therefore allow for lists of entities, lists of ids, single entities and single ids
        if not relationship:
            relationship = []
        elif type(relationship) is str:
            relationship = relationship.split(';')
        elif hasattr(relationship, 'id'):
            relationship = [relationship.id]
        elif type(relationship) is list:
            try:
                relationship = [rel.id for rel in relationship]
            except AttributeError:
                pass

        # make sure that ids in the relationship list are unique
        for rel in relationship:
            if rel not in self._relationship_list:
                self._relationship_list.append(rel)

    @property
    def name(self):
        return self._attrs['name']

    def add_relationships(self, relationship):
        self._add(relationship)
        self.update_in_store()

    def remove_relationship(self, relationship):
        if type(relationship) is Entity:
            relationship = relationship.id

        try:
            assert relationship in self._relationship_list
        except AssertionError:
            raise ValueError('Relationship with {} does not exist'.format(relationship))

        self._relationship_list.remove(relationship)
        self.update_in_store()

    @property
    def relationships(self):
        return self._relationship_list


    def _check_args(self, **kwargs):
        """
        Checks whether the arguments are in the required structure
        :param kwargs: arguments
        :return: None
        """

        for arg in kwargs.keys():
            if arg == self.RELATIONSHIP_ATTR and (kwargs[arg] is None or type(kwargs[arg]) is list):
                continue
            if type(kwargs[arg]) not in self.ALLOWED_TYPES:
                raise TypeError('Argument {} has invalid type {}'.format(arg, type(kwargs[arg])))

    def to_df(self):

        dct = {attr: [self._attrs[attr]] for attr in self._attrs.keys()}

        # separate items in the relatioship list with a comma
        relationship_repr = ''
        for rel in self._relationship_list:
            relationship_repr += rel + ';'
        relationship_repr = relationship_repr[:-1]

        # update in dictionary
        dct.update({self.RELATIONSHIP_ATTR: [relationship_repr]})
        return pd.DataFrame(dct)

    @classmethod
    def from_store(cls, id):
        dct = IOController().retrieve_by_id(cls.TYPE, id)

        # check that the group is not nan
        no_relationships = False
        try:
            no_relationships = np.isnan(dct[cls.RELATIONSHIP_ATTR])
        except TypeError:
            pass
        if no_relationships:
            dct.update({cls.RELATIONSHIP_ATTR: None})

        return cls(**dct)


class Person(RelationalEntity):
    """
    Person class
    """

    RELATIONSHIP_ATTR = 'groups'
    TYPE = 'person'

    def __init__(self, store=True, **kwargs):
        super().__init__(store=False, **kwargs)

        if store:
            self.store()

    @property
    def groups(self):
        return self._relationship_list

    def add_to_group(self, group, establish_connection=True):
        self.add_relationships(group)

        # establish the connection in both ways when called actively
        if establish_connection:
            for g in self.groups:
                Group.from_store(g).add_member(self, establish_connection=False)

    def remove_from_group(self, group):
        self.remove_relationship(group)

    def __eq__(self, other):
        return type(other) is Person and self.id == other.id

    def refresh(self):
        # get the current version of the entity from the store
        p = Person.from_store(self.id)
        self._relationship_list = p.relationships
        self._attrs = p.attrs


class Group(RelationalEntity):
    """
    Group class
    """

    RELATIONSHIP_ATTR = 'members'
    TYPE = 'group'

    def __init__(self, store=True, **kwargs):
        super().__init__(store=False, **kwargs)

        if store:
            self.store()

    @property
    def members(self):
        return self._relationship_list

    def add_member(self, person, establish_connection=True):
        self.add_relationships(person)

        # establish the connection in both ways when called actively
        if establish_connection:
            for p in self.members:
                Person.from_store(p).add_to_group(self, establish_connection=False)

    def remove_member(self, person):
        self.remove_relationship(person)

    def __eq__(self, other):
        return type(other) is Group and self.id == other.id

    def refresh(self):
        # get the current version of the entity from the store
        g = Group.from_store(self.id)
        self._relationship_list = g.relationships
        self._attrs = g.attrs
