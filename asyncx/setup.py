from setuptools import setup, find_packages

setup(
    name="asyncx-tools",
    version="0.2.0",
    packages=find_packages(where="."),
    install_requires=[
        "typing-extensions>=4.0.0",
    ],
    author="tikisan",
    author_email="s2501082@sendai-nct.jp",
    description="非同期タスク管理・同期/非同期変換ライブラリ",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/tikipiya/asyncx",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
) 