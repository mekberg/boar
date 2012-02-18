#!/bin/sh

python blobrepo/tests/test_repository.py || { echo "Blobrepo unittests failed"; exit 1; }
python tests/test_workdir.py || { echo "Workdir unittests failed"; exit 1; }
python tests/test_common.py || { echo "common unittests failed"; exit 1; }
python tests/test_boar_common.py || { echo "boar_common unittests failed"; exit 1; }
macrotests/macrotest.sh || { echo "Macrotests failed"; exit 1; }
