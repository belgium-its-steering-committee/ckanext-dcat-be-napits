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
        self.g.add((contact_point, VCARD.hasEmail, URIRef(self._add_mailto(dataset_dict['contact_point_email']))))

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
