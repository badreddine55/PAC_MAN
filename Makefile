install:
	pip install -r requirements.txt

run:
	python3 pac-man.py config.json

debug:
	python3 -m pdb pac-man.py config.json

clean:
	rm -rf */__pycache__ .mypy_cache */.mypy_cache */.pytest_cache */build dist */*.egg-info poetry.lock


lint:
	flake8 .
	mypy . --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs

lint-strict:
	flake8 .
	mypy . --strict