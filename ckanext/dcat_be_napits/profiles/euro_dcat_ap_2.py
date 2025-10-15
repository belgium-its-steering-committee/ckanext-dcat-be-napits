from datetime import date

from rdflib import Literal, URIRef, BNode, Graph
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

from ckanext.dcat.utils import resource_uri, catalog_uri
from ckanext.dcat.profiles.euro_dcat_ap_2 import EuropeanDCATAP2Profile as CkanEuropeanDCATAP2Profile

from ckanext.dcat_be_napits.utils import catalog_record_uri, publisher_uri_organization_fallback

ORG = Namespace("http://www.w3.org/ns/org#")

namespaces = {
    "org": ORG,
}

SUPPORTED_LANGUAGES_MAP = {
    'en': 'http://publications.europa.eu/resource/authority/language/ENG',
    'nl': 'http://publications.europa.eu/resource/authority/language/NLD',
    'fr': 'http://publications.europa.eu/resource/authority/language/FRA',
    'de': 'http://publications.europa.eu/resource/authority/language/DEU'
}

PREFIX_TEL = "tel:"

class EuropeanDCATAP2Profile(CkanEuropeanDCATAP2Profile):
    """
    Some elements don't get converted correctly by ckan dcat upstream.
    Probably because of some custom modelling in transportdata ckan.
    Correct them here
    """

    def _add_tel(self, tel):
        """
        Ensures that the phone number has an URIRef-compatible tel: prefix.
        Can be used as modifier function for `_add_triple_from_dict`.
        """
        if tel:
            return PREFIX_TEL + self._without_tel(tel)
        else:
            return tel

    def _without_tel(self, tel):
        """
        Ensures that the phone number string has no tel: prefix.
        """
        if tel:
            return str(tel).replace(PREFIX_TEL, "")
        else:
            return tel

    def _clean_license_type_uri(self, uri):
        # https://github.com/belgium-its-steering-committee/ckanext-benap/blob/00b38cdacf4efd44a2556048098a92dda0dfe7ad/ckanext/benap/helpers/lists.py#L1194
        if uri.startswith("http"):
            return uri
        return None

    def _clean_empty_multilang_strings(self):
        """
        Our db multilang fields are all preset with empty strings (unsure if feature or bug).
        Upstream CKAN DCAT doesn't check for empty strings in multilang fields (https://github.com/ckan/ckanext-dcat/blob/dd3b1e8deaea92d8a789e3227882203a47ce650f/ckanext/dcat/profiles/base.py#L1086)
        clean up empty strings in RDF here
        """
        for locale in SUPPORTED_LANGUAGES_MAP.keys():
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
        ]
        self._add_triples_from_dict(dataset_dict, contact_point, items)
        self._add_triple_from_dict(dataset_dict, contact_point, VCARD.hasEmail, 'contact_point_email', _type=URIRef, value_modifier=self._add_mailto)
        self._add_triple_from_dict(dataset_dict, contact_point, VCARD.hasTelephone, 'contact_point_tel', _type=URIRef, value_modifier=self._add_tel)

        # TODO what to do with license info at dataset level vs distribution level. DCAT only has distribution level.
        # example: https://transportdata.be/api/3/action/package_show?id=address-points-belgium-best-address
        for resource_dict in dataset_dict.get("resources", []):
            distribution_ref = CleanedURIRef(resource_uri(resource_dict))

            if resource_dict.get('license_type') or any(resource_dict.get('license_text_translated').values()):
                license_document = BNode()
                self.g.add((license_document, RDF.type, DCT.LicenseDocument))
                self.g.add((distribution_ref, DCT.license, license_document))
                items =[
                    ('license_text_translated', RDFS.label, None, URIRef),
                ]
                self._add_triples_from_dict(resource_dict, license_document, items)
                self._add_triple_from_dict(resource_dict, license_document, DCT.type, 'license_type', _type=URIRef, value_modifier=self._clean_license_type_uri)

            rights_statement = BNode()
            self.g.add((rights_statement, RDF.type, DCT.RightsStatement))
            self.g.add((distribution_ref, DCT.rights, rights_statement))
            items =[
                ('conditions_access', DCT.type, None, URIRef),
                ('conditions_usage', DCT.type, None, URIRef),
                ('additional_info_access_usage_translated', RDFS.label, None, Literal),
            ]
            self._add_triples_from_dict(resource_dict, rights_statement, items)

        # Fix inherited location: is bounding box, not geometry
        # TODO: make filter more specific
        for subject, predicate, object in self.g.triples((None, LOCN.geometry, None)):
            self.g.remove((subject, predicate, object))
            self.g.add((subject, DCAT.bbox, object))

        self._clean_empty_multilang_strings()

        # from pprint import pprint
        # pprint(dataset_dict)

        return

    def _dataset_languages(self, dataset_dict):
        """
        Method for determinine the languages used in dataset *metadata*
        """
        key = 'notes_translated' #  We use the available languages for dataset description as metric
        languages = []
        for lang, value in dataset_dict[key].items():
            if value:
                languages.append(SUPPORTED_LANGUAGES_MAP[lang])
        return languages

    def _generate_ngi_catalog_publisher(self):
        """
        Referencing the existing CKAN NGI org as DCAT catalog publisher would be close,
        but "NGI" is not exactly the desired wording. To be more precise, it is "NGI on behalf of benap ..."
        Therefore we generate a new entity representing that here.
        We can reuse the NGI address though.
        """
        catalog_pub_graph = Graph()
        catalog_pub_uuid = "6df0157c-6022-408f-8c7d-991b9c79466f"  # no reference in DB. Just hardcoded here.
        uri = '{0}/organization/{1}'.format(catalog_uri().rstrip('/'),
                                            catalog_pub_uuid)
        name = Literal("The Belgian National Geographic Institute on behalf of the Belgian ITS steering committee", lang="en")
        catalog_pub = catalog_pub_graph.resource(uri)
        catalog_pub.add(RDF.type, FOAF.Organization)
        catalog_pub.add(FOAF.name, name)
        catalog_pub.add(LOCN.address, URIRef("https://transportdata.be/organization/82e1025c-4db4-4a9c-95f6-e474db508f3f/address"))
        catalog_pub.add(FOAF.mbox, URIRef("mailto:contact@transportdata.be"))
        return catalog_pub_graph, catalog_pub

    def graph_from_catalog(self, catalog_dict, catalog_ref):
        super(EuropeanDCATAP2Profile, self).graph_from_catalog(catalog_dict, catalog_ref)

        # TODO: from upstream, DCT.description should come from ckan.site_description config.
        self.g.add((catalog_ref, DCT.description, Literal("Transportdata.be is the national access point for all mobility related data in Belgium.", lang="en")))

        # DCT.language uses locale default, which is "en". Should be dct:LinguisticSystem controlled voc
        # language used in the user interface of the mobility data portal
        for lang in self.g.objects(catalog_ref, DCT.language):
            self.g.remove((catalog_ref, DCT.language, lang))
        for lang in SUPPORTED_LANGUAGES_MAP.values():
            self.g.add((catalog_ref, DCT.language, URIRef(lang)))
            self.g.add((URIRef(lang), RDF.type, DCT.LinguisticSystem))

        # Add Catalog publisher
        ngi_its_graph, ngi_its = self._generate_ngi_catalog_publisher()
        for triple in ngi_its_graph:
            self.g.add(triple)
        self.g.add((catalog_ref, DCT.publisher, ngi_its.identifier))

        license_document = BNode()
        self.g.add((license_document, RDF.type, DCT.LicenseDocument))
        self.g.add((license_document, DCT.type, URIRef("http://publications.europa.eu/resource/authority/licence/CC0")))
        self.g.add((catalog_ref, DCT.license, license_document))

        self.g.add((catalog_ref, DCT.issued, Literal(date(2020, 2, 14))))

        self.g.add((catalog_ref, DCAT.themeTaxonomy, URIRef("http://publications.europa.eu/resource/authority/data-theme")))

    def graph_from_catalog_record(self, dataset_dict, dataset_ref, catalog_record_ref):
        super(EuropeanDCATAP2Profile, self).graph_from_catalog_record(dataset_dict, dataset_ref, catalog_record_ref)
        g = self.g

        for prefix, namespace in namespaces.items():
            g.bind(prefix, namespace)

        for lang in self._dataset_languages(dataset_dict):
            g.add((URIRef(catalog_record_ref), DCT.language, URIRef(lang)))
            g.add((URIRef(lang), RDF.type, DCT.LinguisticSystem))
