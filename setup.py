from setuptools import setup

with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

setup(
    name="eui",
    version="0.0.2",
    keywords=["pip", "eui"],
    description="a fast and simple micro-framework for small browser-based applications",
    long_description=long_description,
    long_description_content_type='text/markdown',  # This is important!
    license="MIT Licence",

    url="https://github.com/lixk/eui",
    author="Xiangkui Li",
    author_email="1749498702@qq.com",
    py_modules=['eui'],
    # packages=find_packages(),
    # include_package_data=True,
    platforms="any",
    install_requires=[]
)
