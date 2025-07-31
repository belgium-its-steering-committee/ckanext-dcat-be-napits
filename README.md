[![Tests](https://github.com/belgium-its-steering-committee/ckanext-dcat-be-napits/workflows/Tests/badge.svg?branch=main)](https://github.com/belgium-its-steering-committee/ckanext-dcat-be-napits/actions)

# ckanext-dcat-be-napits

A CKAN extension implementing the DCAT requirements of [app-transportdata](https://github.com/belgium-its-steering-committee/app-transportdata). Extends [ckanext-dcat](https://github.com/ckan/ckanext-dcat/). This extension does mainly 2 things:
- Adapt the DCAT-AP2 profile inherited from ckanext-dcat to fit app-transportdata's custom datamodel
- Implement [MobilityDCAT-AP](https://mobilitydcat-ap.github.io/mobilityDCAT-AP/releases/index.html)

This extension currently requires [a fork](https://github.com/belgium-its-steering-committee/ckanext-dcat) of `ckanext-dcat`. This is because the MobilityDCAT-AP spec makes `dcat:CatalogRecord` mandatory and the upstream DCAT extension doesn't support this feature yet. A [PR proposing this feature upstream](https://github.com/ckan/ckanext-dcat/pull/353) has been made.

## Requirements

Compatibility with core CKAN versions:

| CKAN version    | Compatible?   |
| --------------- | ------------- |
| 2.9 and earlier | no            |
| 2.10            | not tested    |
| 2.11            | yes           |


## Config settings

The extension defines the DCAT profiles that it publishes in [pyproject.toml](/pyproject.toml) under `[project.entry-points."ckan.rdf.profiles"]`. Currently available profiles are:
- `euro_mobility_dcat_ap`

In order to make this profile the default, configure the following in the project `.env`:

```
CKANEXT__DCAT__RDF__PROFILES=euro_mobility_dcat_ap
```


## Developer installation

- Move this extension repo folder into `app-transportdata/src`
- Use the `bin/compose` development setup there
- Run `bin/install_src`

Live code reloading should now be active.

## Tests

To run the tests, do:

    pytest --ckan-ini=test.ini


## Releasing a new version of ckanext-dcat-be-napits

If ckanext-dcat-be-napits should be available on PyPI you can follow these steps to publish a new version:

1. Update the version number in the `pyproject.toml` file. See [PEP 440](http://legacy.python.org/dev/peps/pep-0440/#public-version-identifiers) for how to choose version numbers.

2. Make sure you have the latest version of necessary packages:

    pip install --upgrade setuptools wheel twine

3. Create a source and binary distributions of the new version:

       python -m build && twine check dist/*

   Fix any errors you get.

4. Upload the source distribution to PyPI:

       twine upload dist/*

5. Commit any outstanding changes:

       git commit -a
       git push

6. Tag the new release of the project on GitHub with the version number from
   the `setup.py` file. For example if the version number in `setup.py` is
   0.0.1 then do:

       git tag 0.0.1
       git push --tags

## License

[AGPL](https://www.gnu.org/licenses/agpl-3.0.en.html)
