name: Big Dominio Reposter

on:
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: big-dominio-reposter
  cancel-in-progress: false

jobs:
  run:
    runs-on: ubuntu-latest

    env:
      BSKY_USERNAME: ${{ secrets.BSKY_USERNAME }}
      BSKY_PASSWORD: ${{ secrets.BSKY_PASSWORD }}

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install atproto

      - name: Run Big Dominio Reposter
        run: python big_dominio_reposter.py