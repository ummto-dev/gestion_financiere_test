from setuptools import setup, find_packages

setup(
    name="gestion_financiere",
    version="0.0.1",
    description="Application de gestion financiere avec ERPNext/Frappe",
    author="UMMTO",
    author_email="systeme@ummto.dz",
    packages=find_packages(),
    include_package_data=True,
    install_requires=["frappe"],
    zip_safe=False
)
