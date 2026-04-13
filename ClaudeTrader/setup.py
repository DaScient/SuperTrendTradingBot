"""
ClaudeTrader Setup Script
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""

setup(
    name="claudetrader",
    version="1.0.0",
    author="DASCIENT, LLC",
    author_email="info@dascient.com",
    description="Advanced AI-Powered Trading Intelligence System",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/DaScient/SuperTrendTradingBot",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
        "Topic :: Office/Business :: Financial :: Investment",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.9",
    install_requires=[
        "numpy>=1.24.0",
        "pandas>=2.0.0",
        "pyyaml>=6.0",
        "ccxt>=4.0.0",
        "requests>=2.31.0",
        "flask>=3.0.0",
        "flask-cors>=4.0.0",
        "scikit-learn>=1.3.0",
        "scipy>=1.11.0",
        "matplotlib>=3.7.0",
        "seaborn>=0.12.0",
        "plotly>=5.14.0",
        "python-dateutil>=2.8.0",
        "pytz>=2023.3",
        "rich>=13.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "jupyter>=1.0.0",
            "notebook>=7.0.0",
            "ipython>=8.12.0",
        ],
        "llm": [
            "anthropic>=0.18.0",
            "openai>=1.0.0",
        ],
        "rag": [
            "chromadb>=0.4.0",
            "sentence-transformers>=2.2.0",
        ],
        "nlp": [
            "transformers>=4.30.0",
            "torch>=2.0.0",
        ],
        "all": [
            "anthropic>=0.18.0",
            "openai>=1.0.0",
            "chromadb>=0.4.0",
            "sentence-transformers>=2.2.0",
            "transformers>=4.30.0",
            "torch>=2.0.0",
            "websockets>=11.0",
            "flask-jwt-extended>=4.5.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "claudetrader=core.engine:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.yaml", "*.json", "*.md"],
    },
    keywords="trading ai llm rag machine-learning finance cryptocurrency",
    project_urls={
        "Bug Reports": "https://github.com/DaScient/SuperTrendTradingBot/issues",
        "Source": "https://github.com/DaScient/SuperTrendTradingBot",
        "Documentation": "https://github.com/DaScient/SuperTrendTradingBot/tree/main/ClaudeTrader/docs",
    },
)
