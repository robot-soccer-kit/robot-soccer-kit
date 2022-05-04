
format:
	black -l 127 rsk/

all:
	@rm -rf dist/*
	python3 setup.py sdist bdist_wheel

upload:
	python3 -m twine upload --repository pypi dist/*

upload-test:
	python3 -m twine upload --repository testpypi dist/*

clean:
	rm -rf build dist robot_soccer_kit.egg-info
