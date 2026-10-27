# Temporary: checks the backend CI job turns red. Reverted in the next commit.
def test_deliberately_fails():
    assert False, "deliberate failure to check the backend CI job turns red"
