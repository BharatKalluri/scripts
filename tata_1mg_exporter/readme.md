# Tata 1mg report data exporter

This script is a piece from [the health protocol](https://notes.bharatkalluri.com/protocols-health/)

## Why?

I can't export *my report data* which *I paid for* and *got done on myself* from tata 1mg in a parseable format to use
it later for analysis. Why?

## How to run?

```shell
poetry run python ./main.py --help
```

Tata 1mg does not make this easy. They have an API to get health records, but you'll need to pretend to be logging in
from a mobile browser in IOS.

So, change your user agent. Follow instructions on the help guide to get the required fields & trigger the script. It'll
output a csv.
