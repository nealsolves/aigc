"""Allow ``python -m aigc`` to run the CLI."""

import sys
from aigc._internal.cli import main

sys.exit(main())
