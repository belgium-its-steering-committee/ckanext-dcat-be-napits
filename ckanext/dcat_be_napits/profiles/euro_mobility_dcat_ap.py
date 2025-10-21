from rdflib import Literal, URIRef, BNode
from rdflib.namespace import Namespace
import json

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
from ckanext.dcat.utils import resource_uri
from .euro_dcat_ap_2 import EuropeanDCATAP2Profile
from ckanext.dcat_be_napits.utils import publisher_uri_organization_address

MOBILITYDCATAP = Namespace("https://w3id.org/mobilitydcat-ap#")
ORG = Namespace("http://www.w3.org/ns/org#")
CNT = Namespace("http://www.w3.org/2011/content#")
OA = Namespace("https://www.w3.org/ns/oa#")
DC = Namespace("http://purl.org/dc/elements/1.1/")
DQV = Namespace("http://www.w3.org/ns/dqv#")

namespaces = {
    "mobilitydcatap": MOBILITYDCATAP,
    "org": ORG,
    "cnt": CNT,
    "oa": OA,
    "dc": DC,
    "dqv": DQV,
}

EURO_SCHEME_URI_NUTS = "http://data.europa.eu/nuts"
EURO_SCHEME_URI_COUNTRY = "http://publications.europa.eu/resource/authority/country"
CONCEPT_URI_BEL = "http://publications.europa.eu/resource/authority/country/BEL"

class EuropeanMobilityDCATAPProfile(EuropeanDCATAP2Profile):
    """
https://mobilitydcat-ap.github.io/mobilityDCAT-AP/releases/index.html
    """

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

    def _fix_epsg_uri(self, uris):
        """
        CRS URI's with https scheme should have http scheme instead
        TODO: needs fixing in source data, but is patched here
        """
        fixed_uris = []
        for uri in uris:
            if uri.startswith("https://www.opengis.net/def/crs/EPSG"):
                fixed_uri = uri.replace("https://", "http://")
                fixed_uris.append(fixed_uri)
            else:
                fixed_uris.append(uri)
        return fixed_uris

    def graph_from_dataset(self, dataset_dict, dataset_ref):

        super(EuropeanMobilityDCATAPProfile, self).graph_from_dataset(dataset_dict, dataset_ref)

        for prefix, namespace in namespaces.items():
            self.g.bind(prefix, namespace)


        org_id = dataset_dict["organization"]["id"]
        org_dict = self._org_cache[org_id]

        # dcat2 already introduces org as publisher
        org_ref = next(self.g.objects(dataset_ref, DCT.publisher))

        self.g.add((org_ref, RDF.type, FOAF.Organization))
        items =[
            ('title', FOAF.name, None, Literal),
            ('do_website', FOAF.workplaceHomepage, None, URIRef),
        ]
        self._add_triples_from_dict(org_dict, org_ref, items)
        self.g.add((org_ref, FOAF.mbox, URIRef(self._add_mailto(org_dict['do_email']))))
        self.g.add((org_ref, FOAF.phone, URIRef(self._add_tel(org_dict['do_tel']))))
        org_dict['display_title'] = self._suffix_to_fluent_multilang(org_dict, 'display_title', ['en', 'nl', 'fr', 'de'])
        self._add_triple_from_dict(org_dict, org_ref, FOAF.name, 'display_title')

        org_address = CleanedURIRef(publisher_uri_organization_address(dataset_dict))
        self.g.add((org_address, RDF.type, LOCN.Address))
        self.g.add((org_ref, LOCN.address, org_address))

        items =[
            ('country', LOCN.adminUnitL1, None, Literal),
            ('administrative_area', LOCN.adminUnitL2, None, Literal),
            ('postal_code', LOCN.postCode, None, Literal),
            ('city', LOCN.postName, None, Literal),
            ('street_address', LOCN.thoroughfare, None, Literal),
        ]
        self._add_triples_from_dict(org_dict, org_address, items)

        publisher_person = BNode()
        self.g.add((publisher_person, RDF.type, FOAF.Person))

        publisher_name = f"{dataset_dict['publisher_firstname']} {dataset_dict['publisher_surname']}".strip()
        self.g.add((publisher_person, FOAF.name, Literal(publisher_name)))
        items =[
            ('publisher_firstname', FOAF.firstName, None, Literal),
            ('publisher_surname', FOAF.surname, None, Literal),
        ]
        self._add_triples_from_dict(dataset_dict, publisher_person, items)

        # Cardinality for dct:publisher is 1..1
        # Connect publishing person to publishing org as org:memberOf
        # https://mobilitydcat-ap.github.io/mobilityDCAT-AP/releases/index.html#agent-roles
        self.g.add((publisher_person, ORG.memberOf, org_ref))

        # MobilityDCAT specified to remove dcat:keyword
        for subject, predicate, _object in self.g.triples((dataset_ref, DCAT.keyword, None)):
            self.g.remove((subject, predicate, _object))

        if 'mobility_theme' in dataset_dict:
            hierarchic_themes = json.loads(dataset_dict['mobility_theme'])
            for broader_theme, narrower_themes in hierarchic_themes.items():
                self.g.add((dataset_ref, MOBILITYDCATAP.mobilityTheme, CleanedURIRef(broader_theme)))
                if narrower_themes:
                    for theme in narrower_themes:
                        self._add_list_triple(dataset_ref, MOBILITYDCATAP.mobilityTheme, theme, URIRefOrLiteral)

        if 'fluent_tags' in dataset_dict:
            # TODO: adapt once nonsensical key-name has been changed.
            # semantic meaning is transportation mode
            self._add_triple_from_dict(dataset_dict, dataset_ref, MOBILITYDCATAP.transportMode, 'fluent_tags', list_value=True, _type=URIRef)

        if 'network_coverage' in dataset_dict and len(dataset_dict['network_coverage']):
            # Empty list, or list with only 1 item (that in turn contains the real list ...)
            # TODO: fix strip once data serialization is fixed at source
            network_coverage = dataset_dict['network_coverage'][0].strip("{}")
            # TODO: 2 elements in prod DB have double mustache nesting. Those are considered broken data. Migrate those out
            # _add_list_triple covers legacy comma separated lists
            self._add_list_triple(dataset_ref, MOBILITYDCATAP.networkCoverage, network_coverage, URIRefOrLiteral)

        if 'georeferencing_method' in dataset_dict:
            self._add_triple_from_dict(dataset_dict, dataset_ref, MOBILITYDCATAP.georeferencingMethod, 'georeferencing_method', list_value=True, _type=URIRef)

        if 'nap_type' in dataset_dict:
            # TODO: Literal. Should be skos:Concept (ELI identifier)
            self._add_triple_from_dict(dataset_dict, dataset_ref, DCATAP.applicableLegislation, 'nap_type', list_value=True, _type=Literal)

        if 'reference_system' in dataset_dict:
            # Somewhat unexpected interpretation of dct:conformsTo by MobilityDCAT, but according to spec
            self._add_triple_from_dict(dataset_dict, dataset_ref, DCT.conformsTo, 'reference_system', list_value=True, _type=URIRef, value_modifier=self._fix_epsg_uri)

        if 'qual_ass_translated' in dataset_dict:
            for lang, val in dataset_dict['qual_ass_translated'].items():
                if not val:
                    continue
                quality_annotation = BNode()
                self.g.add((quality_annotation, RDF.type, DQV.QualityAnnotation))
                self.g.add((dataset_ref, DQV.hasQualityAnnotation, quality_annotation))
                body = BNode()
                self.g.add((body, RDF.type, OA.TextualBody))
                self.g.add((body, RDF.value, Literal(val)))
                self.g.add((body, DC["format"], Literal("text/plain")))
                self.g.add((body, DC.language, Literal(lang)))
                self.g.add((quality_annotation, OA.hasBody, body))

        for region in dataset_dict['regions_covered']:
            location = BNode()
            self.g.add((dataset_ref, DCT.spatial, location))
            self.g.add((location, RDF.type, DCT.Location))
            self.g.add((location, SKOS.inScheme, URIRef(EURO_SCHEME_URI_NUTS)))
            self.g.add((location, DCT.identifier, URIRef(region)))

        # dataset_dict['countries_covered'] not included in dct:spatial
        # Handling of international organizations/datasets for all delegated
        # regulations (MMTIS, RTTI, SRTI, SSTP) needs clearing out.

        for resource_dict in dataset_dict.get("resources", []):
            distribution_ref = CleanedURIRef(resource_uri(resource_dict))
            items =[
                ('acc_int', MOBILITYDCATAP.applicationLayerProtocol, None, URIRef),
                ('acc_con', MOBILITYDCATAP.communicationMethod, None, URIRef),
                ('acc_gra', MOBILITYDCATAP.grammar, None, URIRef),
                ('acc_mod', MOBILITYDCATAP.mobilityDataStandard, None, URIRef),
                ('acc_desc', MOBILITYDCATAP.dataFormatNotes, None, Literal),
                ('acc_enc', CNT.characterEncoding, None, Literal),
                ('description_resource_translated', DCT.description, None, Literal),
            ]
            if resource_dict['url_type'] == 'upload':
                items.append(('url', DCAT.downloadURL, None, URIRef))

            self._add_triples_from_dict(resource_dict, distribution_ref, items)

            # MobilityDCAT specifies to remove these
            for subject, predicate, _object in self.g.triples((distribution_ref, DCAT.byteSize, None)):
                self.g.remove((subject, predicate, _object))
            for subject, predicate, _object in self.g.triples((distribution_ref, DCAT.mediaType, None)):
                self.g.remove((subject, predicate, _object))



        self._clean_empty_multilang_strings()

        return

    def graph_from_catalog(self, catalog_dict, catalog_ref):
        super(EuropeanMobilityDCATAPProfile, self).graph_from_catalog(catalog_dict, catalog_ref)

        location = BNode()
        self.g.add((catalog_ref, DCT.spatial, location))
        self.g.add((location, RDF.type, DCT.Location))
        self.g.add((location, SKOS.inScheme, URIRef(EURO_SCHEME_URI_COUNTRY)))
        self.g.add((location, DCT.identifier, URIRef(CONCEPT_URI_BEL)))

    def graph_from_catalog_record(self, dataset_dict, dataset_ref, catalog_record_ref):
        super(EuropeanMobilityDCATAPProfile, self).graph_from_catalog_record(dataset_dict, dataset_ref, catalog_record_ref)

        items =[
            ('metadata_created', DCT.created, None, Literal),
        ]
        self._add_date_triples_from_dict(dataset_dict, catalog_record_ref, items)
