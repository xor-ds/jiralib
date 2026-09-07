from setuptools import setup

setup(
    name="jiralib",
    # version='0.1-SNAPSHOT',
    description="Jira utils",
    author="Den Sokolov",
    author_email="xor@mail.ru",
    packages=["jiralib"],
    package_dir={"": "src"},
    install_requires=[
        "atlassian-python-api",
        "pandas",
        "urllib3",
        "xmltodict",
    ],
)
