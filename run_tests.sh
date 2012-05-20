#!/bin/sh

python blobrepo/tests/test_repository.py || { echo "Blobrepo unittests failed"; exit 1; }
python tests/test_workdir.py || { echo "Workdir unittests failed"; exit 1; }
python tests/test_common.py || { echo "common unittests failed"; exit 1; }
python tests/test_boar_common.py || { echo "boar_common unittests failed"; exit 1; }

echo "Executing local macro tests"
BOAR_TEST_REMOTE_REPO=0 macrotests/macrotest.sh || { echo "Macrotests (local) failed"; exit 1; }
echo "Executing remote macro tests"
BOAR_TEST_REMOTE_REPO=1 macrotests/macrotest.sh || { echo "Macrotests (remote) failed"; exit 1; }
