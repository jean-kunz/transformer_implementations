from importlib.resources import files
from pytest_notebook import example_nbs
from pytest_notebook.nb_regression import NBRegressionFixture

fixture = NBRegressionFixture(exec_timeout=50)
fixture.diff_color_words = False

import os
print(os.getcwd())
fixture.check("./notebooks/tests.ipynb")