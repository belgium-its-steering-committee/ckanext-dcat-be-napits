from rdflib import Literal, URIRef, BNode
from rdflib.namespace import Namespace

import ckantoolkit as toolkit
from ckanext.dcat.profiles.base import URIRefOrLiteral, CleanedURIRef
from ckanext.dcat.profiles.base import (
    CNT,
    CR,
    RDF,
    XSD,
    SKOS,
    RDFS,
    DCAT,
    DCATAP,
    DCATUS,
    DCT,
    ADMS,
    VCARD,
    FOAF,
    SCHEMA,
    LOCN,
    GSP,
    OWL,
    SPDX,
    GEOJSON_IMT,
)
from ckanext.dcat.profiles.euro_dcat_ap_2 import EuropeanDCATAP2Profile as CkanEuropeanDCATAP2Profile
from ckanext.dcat_be_napits.utils import catalog_record_uri, publisher_uri_organization_fallback

ORG = Namespace("http://www.w3.org/ns/org#")

namespaces = {
    "org": ORG,
}

class EuropeanDCATAP2Profile(CkanEuropeanDCATAP2Profile):
    """
    Some elements don't get converted correctly by ckan dcat upstream.
    Probably because of some custom modelling in transportdata ckan.
    Correct them here
    """

    def parse_dataset(self, dataset_dict, dataset_ref):
        dataset_dict = super(EuropeanDCATAP2Profile, self).parse_dataset(
            dataset_dict, dataset_ref
        )
        return dataset_dict

    def _suffix_to_fluent_multilang(self, dataset_dict, key, languages):
        """
        'display_title_de': 'Nationales Geographisches Institut',
        'display_title_en': 'National Geographic Institute ',
        to
        {
            'de': 'Nationales Geographisches Institut',
            'en': 'National Geographic Institute '
        }
        """
        fluent_multilang = {}
        for lang in languages:
            suffix_key = f"{key}_{lang}"
            val = dataset_dict.get(suffix_key)
            if val:
                fluent_multilang[lang] = val
        return fluent_multilang

    def _clean_empty_multilang_strings(self):
        """
        Our db multilang fields are all preset with empty strings (unsure if feature or bug).
        Upstream CKAN DCAT doesn't check for empty strings in multilang fields (https://github.com/ckan/ckanext-dcat/blob/dd3b1e8deaea92d8a789e3227882203a47ce650f/ckanext/dcat/profiles/base.py#L1086)
        clean up empty strings in RDF here
        """
        locales = ['en', 'nl', 'fr', 'de'] # TODO: get this from config
        for locale in locales:
            for subject, predicate, object in self.g.triples((None, None, Literal("", lang=locale))):
                self.g.remove((subject, predicate, object))

    def graph_from_dataset(self, dataset_dict, dataset_ref):
        super(EuropeanDCATAP2Profile, self).graph_from_dataset(dataset_dict, dataset_ref)

        for prefix, namespace in namespaces.items():
            self.g.bind(prefix, namespace)

        # semanctics: form field info for contact details says
        # "The "contact point", describes an organisation, if applicable a person, which is responsible for the creation and maintenance of the metadata. This person or organization is the single point of contact for the present metadata set. "
        contact_point = BNode()
        self.g.add((contact_point, RDF.type, VCARD.Kind))
        self.g.add((dataset_ref, DCAT.contactPoint, contact_point))

        items =[
            ('contact_point_name', VCARD.fn, None, Literal),
            ('contact_point_tel', VCARD.tel, None, Literal),
        ]
        self._add_triples_from_dict(dataset_dict, contact_point, items)
        self._add_triple_from_dict(dataset_dict, contact_point, VCARD.hasEmail, 'contact_point_email', _type=URIRef, value_modifier=self._add_mailto)

        for dcat_distribution in self._distributions(dataset_ref):
            # TODO what to do with license info at dataset level vs distribution level. DCAT only has distribution level.
            # example: https://transportdata.be/api/3/action/package_show?id=address-points-belgium-best-address
            distribution = dataset_dict['resources'][0]
            license_document = BNode()
            self.g.add((license_document, RDF.type, DCT.LicenseDocument))
            self.g.add((dcat_distribution, DCT.license, license_document))
            self._add_triple_from_dict(distribution, license_document, DCT.identifier, 'license_type', _type=URIRef) # Mobilitydcat specific
            # TODO: remove empty values for multilang until upstream dcat fixed
            self._add_triple_from_dict(distribution, license_document, RDFS.label, 'license_text_translated')

        for dcat_distribution in self._distributions(dataset_ref):
            distribution = dataset_dict['resources'][0]
            rights_statement = BNode()
            self.g.add((rights_statement, RDF.type, DCT.RightsStatement))
            self.g.add((dcat_distribution, DCT.rights, rights_statement))
            self._add_triple_from_dict(distribution, rights_statement, DCT.type, 'conditions_access', _type=URIRef) # Mobilitydcat specific
            self._add_triple_from_dict(distribution, rights_statement, DCT.type, 'conditions_usage', _type=URIRef) # Mobilitydcat specific
            self._add_triple_from_dict(distribution, rights_statement, RDFS.label, 'additional_info_access_usage_translated') # Mobilitydcat specific

        # Fix inherited location: is bounding box, not geometry
        # TODO: make filter more specific
        for subject, predicate, object in self.g.triples((None, LOCN.geometry, None)):
            self.g.remove((subject, predicate, object))
            self.g.add((subject, DCAT.bbox, object))

        self._clean_empty_multilang_strings()

        return

    def _dataset_languages(self, dataset_dict):
        """
        Method for determinine the languages used in dataset *metadata*
        """
        key = 'notes_translated' #  We use the available languages for dataset description as metric
        langmap = {
            'en': 'http://publications.europa.eu/resource/authority/language/ENG',
            'nl': 'http://publications.europa.eu/resource/authority/language/NLD',
            'fr': 'http://publications.europa.eu/resource/authority/language/FRA',
            'de': 'http://publications.europa.eu/resource/authority/language/DEU'
        }
        languages = []
        for lang, value in dataset_dict[key].items():
            if value:
                languages.append(langmap[lang])
        return languages

    def graph_from_catalog(self, catalog_dict, catalog_ref):
        super(EuropeanDCATAP2Profile, self).graph_from_catalog(catalog_dict, catalog_ref)

        # TODO: DCT.description should come from ckan.site_description config.
        # TODO: DCT.language uses locale default, which is "en", this can be improved
        # TODO: DCAT.record: CatalogRecord for the Catalog

        # Add NGI as Catalog publisher
        # If we want transportdata email address instead, then we'll have to duplicate this entity
        NGI_ID = "82e1025c-4db4-4a9c-95f6-e474db508f3f"
        ngi_dict = toolkit.get_action('organization_show')({}, {'id': NGI_ID})
        dataset_dict = {'organization': ngi_dict}
        ngi_uri = CleanedURIRef(publisher_uri_organization_fallback(dataset_dict))
        self.g.add((catalog_ref, DCT.publisher, ngi_uri))

    def graph_from_catalog_record(self, dataset_dict, catalog_record_ref, dataset_ref):
        # TODO: Handling addition of dcat:CatalogRecord's should probably be done in the serializer.
        # analyze if it is possible to extend serializer in extension
        # https://github.com/ckan/ckanext-dcat/blob/dd3b1e8deaea92d8a789e3227882203a47ce650f/ckanext/dcat/processors.py#L355
        # since we don't have access to dataset_dict's here, the catalog records are pre-generated

        g = self.g

        if not catalog_record_ref:
            catalog_record_ref = CleanedURIRef(catalog_record_uri(dataset_dict))

        for prefix, namespace in namespaces.items():
            g.bind(prefix, namespace)

        g.add((catalog_record_ref, RDF.type, DCAT.CatalogRecord))
        g.add((catalog_record_ref, FOAF.primaryTopic, dataset_ref))
        # TODO: inherited method sets dct:modified with metadata_modified too
        # This might be semanctically incorrect, as this should pertain to the content of the dataset
        items =[
            ('metadata_created', DCT.created, None, Literal),
            ('metadata_modified', DCT.modified, None, Literal),
        ]
        self._add_date_triples_from_dict(dataset_dict, catalog_record_ref, items)
        for lang in self._dataset_languages(dataset_dict):
            g.add((URIRef(catalog_record_ref), FOAF.language, URIRef(lang)))
