NAME = script-assess
SCRIPTS_DIR_NAME = script_assess
VERSION = $(shell git tag | sort -V | tail -n 1)

DIR_NAME_VERSION = $(NAME)-$(VERSION)
NAME_VERSION = $(DEST_DIR)/$(DIR_NAME_VERSION)
TARBALL = $(NAME_VERSION).tar

P_SWAMP=/p/swamp

DEST_DIR = $(P_SWAMP)/home/vamshi/mnt/v1/releases
DEST_DIR = tmp


SWAMP_FW=$(P_SWAMP)/frameworks

SWAMP_FW_PY=$(SWAMP_FW)/python

SWAMP_FW_WEB=$(SWAMP_FW)/web
SWAMP_FW_PHP=$(SWAMP_FW_WEB)/php
SWAMP_FW_NODE=$(SWAMP_FW_WEB)/node.js
SWAMP_FW_COMPOSER=$(SWAMP_FW_WEB)/composer

## location of python binaries
PYTHON_2_BINARIES=$(SWAMP_FW_PY)/python-2-arch
PYTHON_3_BINARIES=$(SWAMP_FW_PY)/python-3-arch

## name of python binary to insert
PYTHON_2_BINARY=python-2-bin.tar.gz
PYTHON_3_BINARY=python-3-bin.tar.gz

## where it is
PYTHON_2_FULLPATH=$(PYTHON_2_BINARIES)/$(PLAT)/$(PYTHON_2_BINARY)
PYTHON_3_FULLPATH=$(PYTHON_3_BINARIES)/$(PLAT)/$(PYTHON_3_BINARY)

## Platform update tool
UPDATE_PLATFORM=$(SWAMP_FW)/platform/update-platform

MAKE_MD5SUM = find -P $(NAME_VERSION) -type f -not -name md5sum \
    -exec md5sum '{}' '+' > $(NAME_VERSION)/md5sum


## From now one, the framework selects which version to use,
## so changes to the framework node.js do not change the
## assessment framework inadvertently


## current LTS
NODE_MAJOR=10
NODE_VERSION=10.16.3
NODE_32=false

## old LTS
NODE_MAJOR=8
NODE_VERSION=8.16.1
NODE_32=true

NODE_DIR=$(SWAMP_FW_NODE)/node-$(NODE_MAJOR)
NODE_VNAME_PFX=node-v$(NODE_VERSION)-linux

NODE_64_BINARY=$(NODE_VNAME_PFX)-x64.tar.gz
NODE_32_BINARY=$(NODE_VNAME_PFX)-x86.tar.gz

NODE_64_FULLPATH = $(NODE_DIR)/$(NODE_64_BINARY)
NODE_32_FULLPATH = $(NODE_DIR)/$(NODE_32_BINARY)


## And now composer is versioned as well.

## version in use since Jan 2017
COMPOSER_VER=1.1.0

## new version I am testing in 2019
COMPOSER_VER=1.9.0

COMPOSER_VNAME=composer-$(COMPOSER_VER)

COMPOSER_PHAR=$(SWAMP_FW_COMPOSER)/$(COMPOSER_VNAME)/composer.phar

## and the php initialization is hardwired too, no versions yet
PHP_INI=$(SWAMP_FW_PHP)/php.ini

MK_ALIAS_PLAT=$(PWD)/mk-alias-plat

include Makefile.plats

default: all

all: tarball 

tarball: $(TARBALL)

redo-tarball:
	(cd $(DEST_DIR) ; tar cf $(DIR_NAME_VERSION).tar $(DIR_NAME_VERSION))

$(TARBALL): $(NAME_VERSION) $(NAME_VERSION)/md5sum
	(cd $(DEST_DIR) ; tar cf $(DIR_NAME_VERSION).tar $(DIR_NAME_VERSION))

redo-md5sum:
	rm -f $(NAME_VERSION)/md5sum
	$(MAKE) md5sum

md5sum: $(NAME_VERSION)/md5sum

$(NAME_VERSION)/md5sum:
	(cd $(NAME_VERSION) ; find -P . -type f -not -name md5sum \
		-exec md5sum '{}' '+' >md5sum)


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

	@tar cf - -C build_monitors . | tar xfp - -C $(NAME_VERSION)/$(BASE_PLAT)/in-files/scripts/
	@tar cf - -C build_monitors_obj . | tar xfp - -C $(NAME_VERSION)/$(BASE_PLAT)/in-files/scripts/

	@cp -r -p lib/* $(NAME_VERSION)/$(BASE_PLAT)/in-files/scripts/lib
	@cp -r -p $(SWAMP_FW_WEB)/lib/* $(NAME_VERSION)/$(BASE_PLAT)/in-files/scripts/lib
	@cp -r -p src/* $(NAME_VERSION)/$(BASE_PLAT)/in-files/scripts/lib/$(SCRIPTS_DIR_NAME)
	@mkdir $(NAME_VERSION)/$(BASE_PLAT)/in-files/scripts/lib/version
	@: > $(NAME_VERSION)/$(BASE_PLAT)/in-files/scripts/lib/version/__init__.py
	@echo $(VERSION) > $(NAME_VERSION)/$(BASE_PLAT)/in-files/scripts/lib/version/version.txt
	@echo $(VERSION) > $(NAME_VERSION)/$(BASE_PLAT)/in-files/build_assess_driver_version.txt
	@cd $(NAME_VERSION)/$(BASE_PLAT)/in-files && tar cz -f scripts.tar.gz scripts && rm -rf scripts

	@cp -r -p $(NODE_64_FULLPATH) $(NAME_VERSION)/$(BASE_PLAT)/in-files

ifeq ($(NODE_32),true)
	@cp -r -p $(NODE_32_FULLPATH) $(NAME_VERSION)/$(BASE_PLAT)/in-files
endif

	@sed --in-place "s@NODE_64_BINARY@$(NODE_64_BINARY)@" $(NAME_VERSION)/$(BASE_PLAT)/in-files/build_assess_driver

ifeq ($(NODE_32),true)
	@sed --in-place "s@NODE_32_BINARY@$(NODE_32_BINARY)@" $(NAME_VERSION)/$(BASE_PLAT)/in-files/build_assess_driver
endif

	@cp -r -p $(COMPOSER_PHAR) $(NAME_VERSION)/$(BASE_PLAT)/in-files

	@cp -r -p $(PHP_INI) $(NAME_VERSION)/$(BASE_PLAT)/in-files

	@$(UPDATE_PLATFORM) --framework python --dir $(NAME_VERSION)/$(BASE_PLAT)/in-files

## don't try to put binaries in arch-independent things
ifneq ($(BASE_PLAT),noarch)
ifneq ($(BASE_PLAT),common)
	@echo '	'python2
	@cp -p $(PYTHON_2_FULLPATH)	\
		$(NAME_VERSION)/$(BASE_PLAT)/in-files
	@echo '	'python3
	@cp -p $(PYTHON_3_FULLPATH)	\
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
		cp -p $(PYTHON_2_FULLPATH) $(NAME_VERSION)/$(PLAT)/in-files;\
		echo '	'python3; \
		cp -p $(PYTHON_3_FULLPATH) $(NAME_VERSION)/$(PLAT)/in-files;\
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

