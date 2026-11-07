PY ?= python3

.PHONY: install data test quick all report clean-results

install:
	$(PY) -m pip install -e ".[test]"

data:
	$(PY) -m pqde data

test:
	$(PY) -m pytest -q

# smoke run of every experiment (few trials) into results/_scratch
quick:
	$(PY) -m pqde run e1 e2 e3 e4 e5 --quick --out results/_scratch

# the full set of experiments + results/REPORT.md
all:
	$(PY) -m pqde all

e1 e2 e3 e4 e5:
	$(PY) -m pqde run $@

report:
	$(PY) -c "from pqde.report import build_report; print(build_report())"

clean-results:
	rm -rf results/e1 results/e2 results/e3 results/e4 results/e5 results/REPORT.md results/_scratch
