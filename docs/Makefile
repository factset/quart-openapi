# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line.
SPHINXOPTS    =
SPHINXBUILD   = sphinx-build
SPHINXPROJ    = Quart-OpenAPI
SOURCEDIR     = .
BUILDDIR      = build

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile create-gh-pages clone-gh-pages checkout-gh-pages gh-pages

clone-gh-pages:
	if [ ! -d $(BUILDDIR)/html/.git ] ; then rm -rf $(BUILDDIR)/html ; git clone `git remote -v | head -n 1 | awk '{ print $$2 }'` $(BUILDDIR)/html; fi

create-gh-pages: clone-gh-pages
	cd $(BUILDDIR)/html; git checkout --orphan gh-pages
	cd $(BUILDDIR)/html; git rm -rf .
	touch $(BUILDDIR)/html/.nojekyll
	cd $(BUILDDIR)/html; git add .nojekyll; git commit -m "Create the gh-pages branch"; git push origin gh-pages

define check_git_diff_status
	if [[ ! -z `cd $(BUILDDIR)/html; git status -s` ]]; then \
		cd $(BUILDDIR)/html; git add .; git commit -m "Rebuilt docs"; git push origin gh-pages; \
	fi
endef

checkout-gh-pages: clone-gh-pages
	if [ ! `cd $(BUILDDIR)/html; git branch --all --list | grep 'remotes/origin/gh-pages'` ]; then $(MAKE) create-gh-pages; else cd $(BUILDDIR)/html; git checkout gh-pages; fi

gh-pages: | checkout-gh-pages html
	@$(call check_git_diff_status)

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
