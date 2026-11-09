all:
	@rm -rf dist/*
	python3 -m build

format:
	ruff format rsk/ tests/

test:
	uv run --group dev pytest tests/

upload:
	python3 -m twine upload --repository pypi dist/*

upload-test:
	python3 -m twine upload --repository testpypi dist/*

clean:
	rm -rf build dist robot_soccer_kit.egg-info
