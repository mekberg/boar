set -e

$BOAR import | grep "Usage: boar import" || { echo "Import with no args should give usage information"; exit 1; }
