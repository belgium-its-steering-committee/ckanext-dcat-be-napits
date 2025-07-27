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
from .euro_dcat_ap_2 import EuropeanDCATAP2Profile

MOBILITYDCATAP = Namespace("https://w3id.org/mobilitydcat-ap#")
ORG = Namespace("http://www.w3.org/ns/org#")

namespaces = {
    "mobilitydcatap": MOBILITYDCATAP,
    "org": ORG,
}


class EuropeanMobilityDCATAPProfile(EuropeanDCATAP2Profile):
    """
https://mobilitydcat-ap.github.io/mobilityDCAT-AP/releases/index.html
    """

    def parse_dataset(self, dataset_dict, dataset_ref):
        dataset_dict = super(EuropeanMobilityDCATAPProfile, self).parse_dataset(
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

    def graph_from_dataset(self, dataset_dict, dataset_ref):

        super(EuropeanMobilityDCATAPProfile, self).graph_from_dataset(dataset_dict, dataset_ref)

        for prefix, namespace in namespaces.items():
            self.g.bind(prefix, namespace)


        org_id = dataset_dict.get('organization', {}).get('id')
        org_dict = toolkit.get_action('organization_show')({}, {'id': org_id})

        #check if dcat2 already introduced one publisher
        existing_publishers = self.g.objects(dataset_ref, DCT.publisher)
        if existing_publishers:
            publisher_details = next(existing_publishers)
        else:
            publisher_uri = self._get_dataset_value(dataset_dict, 'publisher_uri')
            if publisher_uri:
                publisher_details = CleanedURIRef(publisher_uri)
            else:
                publisher_details = BNode()

        org = publisher_details # reuses entity created by inherited dcat class
        self.g.add((org, RDF.type, FOAF.Agent))
        self.g.add((org, RDF.type, FOAF.Organization))
        items =[
            ('title', FOAF.name, None, Literal),
            ('do_tel', FOAF.phone, None, Literal),
            ('do_website', FOAF.workplaceHomepage, None, URIRef),
        ]
        self._add_triples_from_dict(org_dict, org, items)
        self.g.add((org, FOAF.mbox, URIRef(self._add_mailto(org_dict['do_email']))))
        org_dict['display_title'] = self._suffix_to_fluent_multilang(org_dict, 'display_title', ['en', 'nl', 'fr', 'de'])
        self._add_triple_from_dict(org_dict, org, FOAF.name, 'display_title')

        org_address = BNode()
        self.g.add((org_address, RDF.type, LOCN.Address))
        self.g.add((publisher_details, LOCN.address, org_address))

        items =[
            ('country', LOCN.adminUnitL1, None, Literal),
            ('administrative_area', LOCN.adminUnitL2, None, Literal),
            ('postal_code', LOCN.postCode, None, Literal),
            ('city', LOCN.postName, None, Literal),
            ('street_address', LOCN.thoroughfare, None, Literal),
        ]
        self._add_triples_from_dict(org_dict, org_address, items)

        publisher_person = BNode()
        self.g.add((publisher_person, RDF.type, FOAF.Agent))
        self.g.add((publisher_person, RDF.type, FOAF.Person))
        self.g.add((dataset_ref, DCT.publisher, publisher_person))

        publisher_name = f"{dataset_dict['publisher_firstname']} {dataset_dict['publisher_surname']}".strip()
        self.g.add((publisher_person, FOAF.name, Literal(publisher_name)))
        items =[
            ('publisher_firstname', FOAF.firstName, None, Literal),
            ('publisher_surname', FOAF.surname, None, Literal),
        ]
        self._add_triples_from_dict(dataset_dict, publisher_person, items)
        self.g.add((publisher_person, ORG.memberOf, org))


        if 'mobility_theme' in dataset_dict:
            hierarchic_themes = json.loads(dataset_dict['mobility_theme'])
            for broader_theme, narrower_themes in hierarchic_themes.items():
                if narrower_themes:
                    for theme in narrower_themes:
                        self._add_list_triple(dataset_ref, MOBILITYDCATAP.mobilityTheme, theme, URIRefOrLiteral)
                else:
                    self.g.add((dataset_ref, MOBILITYDCATAP.mobilityTheme, CleanedURIRef(broader_theme)))

        if 'fluent_tags' in dataset_dict:
            # TODO: adapt once nonsensical key-name has been changed.
            # semantic meaning is transportation mode
            self._add_triple_from_dict(dataset_dict, dataset_ref, MOBILITYDCATAP.transportMode, 'fluent_tags', list_value=True, _type=URIRef)

        if 'network_coverage' in dataset_dict:
            # Always a list with only 1 item (that in turn contains the real list ...)
            # TODO: fix strip once data serialization is fixed at source
            network_coverage = dataset_dict['network_coverage'][0].strip("{}")
            # TODO: 2 elements in prod DB have double mustache nesting. Those are considered broken data. Migrate those out
            # _add_list_triple covers legacy comma separated lists
            self._add_list_triple(dataset_ref, MOBILITYDCATAP.networkCoverage, network_coverage, URIRefOrLiteral)

        if 'georeferencing_method' in dataset_dict:
            self._add_triple_from_dict(dataset_dict, dataset_ref, MOBILITYDCATAP.georeferencingMethod, 'georeferencing_method', list_value=True, _type=URIRef)

        # Only if it adds specificity, not if all belgian regions are covered
        if len(dataset_dict['regions_covered']) != 3:
            for region in dataset_dict['regions_covered']:
                location = BNode()
                self.g.add((dataset_ref, DCT.spatial, location))
                self.g.add((location, RDF.type, DCT.Location))
                self.g.add((location, SKOS.inScheme, URIRef("http://data.europa.eu/nuts")))
                self.g.add((location, DCT.identifier, URIRef(region)))

        for country in dataset_dict['countries_covered']:
            BEL = "http://publications.europa.eu/resource/authority/country/BEL"
            if country == BEL and len(dataset_dict['regions_covered']) != 3:
                # only add belgium if regions covered is no more specific
                continue
            location = BNode()
            self.g.add((dataset_ref, DCT.spatial, location))
            self.g.add((location, RDF.type, DCT.Location))
            self.g.add((location, SKOS.inScheme, URIRef("https://publications.europa.eu/resource/authority/country")))
            self.g.add((location, DCT.identifier, URIRef(country)))

        self._clean_empty_multilang_strings()

        return
