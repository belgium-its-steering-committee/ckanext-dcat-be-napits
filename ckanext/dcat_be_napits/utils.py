# -*- coding: utf-8 -*-
import uuid
import logging

from ckanext.dcat.utils import publisher_uri_organization_fallback, dataset_uri, catalog_uri

log = logging.getLogger(__name__)

def publisher_uri_organization_address(dataset_dict):
    '''
    Builds a URI of the form
    `publisher_uri_organization_address()` + '/address'
    '''
    if dataset_dict.get('organization'):
        return '{0}/address'.format(publisher_uri_organization_fallback(dataset_dict))

    return None

def catalog_record_uri(dataset_dict):
    _dataset_uri = dataset_uri(dataset_dict)
    if '/dataset/' in _dataset_uri:
        uri = _dataset_uri.replace('/dataset/', '/catalog-record/')
    else:
        uri = '{0}/catalog-record/{1}'.format(catalog_uri().rstrip('/'),
                                       str(uuid.uuid4()))
        log.warning('Using a random id for catalog record URI')

    return uri
