import sys

import pytest

if __name__ == "__main__":
    # Pass through command line arguments to pytest
    sys.exit(pytest.main(sys.argv[1:]))
