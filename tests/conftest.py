import os

# Enable authentication fallback stubs by default for legacy regression tests
os.environ["ALLOW_AUTH_FALLBACK"] = "True"
