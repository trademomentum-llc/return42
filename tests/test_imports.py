def test_package_imports():
    import return42
    import return42.observability
    assert return42.__version__ == "0.1.0"
