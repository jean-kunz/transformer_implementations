create_mac_env:
	pyenv install 3.11 -s
	pyenv local 3.11
	poetry env use 3.11
	poetry install

install_mac: create_mac_env

test:
	pytest --nb-test-files --log-cli-level debug  notebooks/test.ipynb