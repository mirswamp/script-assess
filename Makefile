NAME = script-assess
SCRIPTS_DIR_NAME = script_assess
VERSION = $(shell git tag | sort -V | tail -n 1)

NAME_VERSION = $(DEST_DIR)/$(NAME)-$(VERSION)
TARBALL = $(NAME_VERSION).tar

P_SWAMP=/p/swamp
DEST_DIR = $(P_SWAMP)/home/vamshi/mnt/v1/releases
SWAMP_FW=$(P_SWAMP)/frameworks
SWAMP_FW_PY=$(SWAMP_FW)/python
SWAMP_FW_PHP=$(SWAMP_FW)/php
SWAMP_FW_NODE=$(SWAMP_FW)/node.js
SWAMP_FW_WEB=$(SWAMP_FW)/web

## location of python binaries
PYTHON_2_BINARIES=$(SWAMP_FW_PY)/python-2-arch
PYTHON_3_BINARIES=$(SWAMP_FW_PY)/python-3-arch

## Platform update tool
UPDATE_PLATFORM=$(SWAMP_FW)/platform/update-platform

MAKE_MD5SUM = find -P $(NAME_VERSION) -type f -not -name md5sum \
    -exec md5sum '{}' '+' > $(NAME_VERSION)/md5sum

NODE_64_FULLPATH = $(shell readlink -e $(SWAMP_FW_NODE)/noarch/node-latest-x64)
NODE_64_BINARY = $(shell basename $(NODE_64_FULLPATH))
NODE_32_FULLPATH = $(shell readlink -e $(SWAMP_FW_NODE)/noarch/node-latest-x86)
NODE_32_BINARY = $(shell basename $(NODE_32_FULLPATH))

MK_ALIAS_PLAT=$(PWD)/mk-alias-plat

include Makefile.plats

default: all

all: tarball 

tarball: $(TARBALL)

$(TARBALL): $(NAME_VERSION)
	$(MAKE_MD5SUM)
# tar -cf $(TARBALL) $(NAME_VERSION)

$(NAME_VERSION): build_monitors/* lib/* src/* ./release/* 
	$(MAKE) base_plat normal_plats alias_plats

## Create a base platform.  If the base platform is a MD-architecture,
## include those files.
base_plat base-plat:
	@echo creating script assess $(VERSION)

	@echo ==== base platform $(BASE_PLAT)

	@mkdir -p $(NAME_VERSION)/$(BASE_PLAT)/in-files
	@mkdir -p $(NAME_VERSION)/$(BASE_PLAT)/swamp-conf

	@cp -p release/LICENSE.txt $(NAME_VERSION)/
	@cp -p release/README.txt $(NAME_VERSION)/
	@cp -p release/RELEASE_NOTES.txt $(NAME_VERSION)/

	@echo '	'swamp-conf
	@cp -p release/swamp-conf/* $(NAME_VERSION)/$(BASE_PLAT)/swamp-conf

	@echo '	'in-files
	@cp -p release/in-files/* $(NAME_VERSION)/$(BASE_PLAT)/in-files


	@mkdir -p $(NAME_VERSION)/$(BASE_PLAT)/in-files/scripts/lib/$(SCRIPTS_DIR_NAME)
	@cp -r -p build_monitors/* $(NAME_VERSION)/$(BASE_PLAT)/in-files/scripts/
	@cp -r -p lib/* $(NAME_VERSION)/$(BASE_PLAT)/in-files/scripts/lib
	@cp -r -p $(SWAMP_FW_WEB)/lib/* $(NAME_VERSION)/$(BASE_PLAT)/in-files/scripts/lib
	@cp -r -p src/* $(NAME_VERSION)/$(BASE_PLAT)/in-files/scripts/lib/$(SCRIPTS_DIR_NAME)
	@mkdir $(NAME_VERSION)/$(BASE_PLAT)/in-files/scripts/lib/version
	@: > $(NAME_VERSION)/$(BASE_PLAT)/in-files/scripts/lib/version/__init__.py
	@echo $(VERSION) > $(NAME_VERSION)/$(BASE_PLAT)/in-files/scripts/lib/version/version.txt
	@cd $(NAME_VERSION)/$(BASE_PLAT)/in-files && tar cz -f scripts.tar.gz scripts && rm -rf scripts
	@cp -r -p $(NODE_64_FULLPATH) $(NAME_VERSION)/$(BASE_PLAT)/in-files
	@cp -r -p $(NODE_32_FULLPATH) $(NAME_VERSION)/$(BASE_PLAT)/in-files

	@sed --in-place "s@NODE_32_BINARY@$(NODE_32_BINARY)@" $(NAME_VERSION)/$(BASE_PLAT)/in-files/build_assess_driver
	@sed --in-place "s@NODE_64_BINARY@$(NODE_64_BINARY)@" $(NAME_VERSION)/$(BASE_PLAT)/in-files/build_assess_driver

	@cp -r -p $(SWAMP_FW_PHP)/noarch/composer.phar $(NAME_VERSION)/$(BASE_PLAT)/in-files
	@cp -r -p $(SWAMP_FW_PHP)/noarch/php.ini $(NAME_VERSION)/$(BASE_PLAT)/in-files

	@$(UPDATE_PLATFORM) --framework python --dir $(NAME_VERSION)/$(BASE_PLAT)/in-files

## don't try to put binaries in arch-independent things
ifneq ($(BASE_PLAT),noarch)
ifneq ($(BASE_PLAT),common)
	@echo '	'python2
	@cp -p $(PYTHON_2_BINARIES)/$(BASE_PLAT)/python-2-bin.tar.gz \
		$(NAME_VERSION)/$(BASE_PLAT)/in-files
	@echo '	'python3
	@cp -p $(PYTHON_3_BINARIES)/$(BASE_PLAT)/python-3-bin.tar.gz \
		$(NAME_VERSION)/$(BASE_PLAT)/in-files
endif
endif
	@cp ./release/README.txt ./release/RELEASE_NOTES.txt $(NAME_VERSION)/



## Normal platforms are symbolic link copies of the base platform which
## over-ride any MD content present in the base platform.
## Because in-files is examines, that is that master reference for symlinks
normal_plats normal-plats:
	@echo ==== secondary platforms
	@$(foreach PLAT,$(NORMAL_PLATS),\
		echo $(PLAT); \
		mkdir -p $(NAME_VERSION)/$(PLAT)/in-files;\
		echo '	'in-files; \
		(cd $(NAME_VERSION)/$(PLAT)/in-files ;\
		find ../../$(BASE_PLAT)/in-files -type f -exec ln -sf '{}' ';' ;);\
		echo '	'swamp-conf; \
		ln -s ../$(BASE_PLAT)/swamp-conf --target-directory=$(NAME_VERSION)/$(PLAT);\
		echo '	'python2; \
		cp -p $(PYTHON_2_BINARIES)/$(PLAT)/python-2-bin.tar.gz $(NAME_VERSION)/$(PLAT)/in-files;\
		echo '	'python3; \
		cp -p $(PYTHON_3_BINARIES)/$(PLAT)/python-3-bin.tar.gz $(NAME_VERSION)/$(PLAT)/in-files;\
	)


## alias platforms are symbolic link references to other platforms
## they are needed either because a new platform exists, or something
## needs to exist hypervisor-side to make things work.
alias_plats alias-plats:
	@echo ==== alias platforms
	@(cd $(NAME_VERSION) && $(MK_ALIAS_PLAT) $(ALIAS_PLATS))


clean:
	rm -rf $(NAME_VERSION) \
		        $(TARBALL)

.PHONY: all tarball clean fullclean

