#!/bin/bash

#
#  run.sh    http://www.cs.wisc.edu/~kupsch
# 
#  Copyright 2013 James A. Kupsch
# 
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
# 
#      http://www.apache.org/licenses/LICENSE-2.0
# 
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

#
# check for broken V2 VMs, delete --------------------------
#
if [ -z "$VMOUTPUTDIR" ]; then
    . /opt/swamp/etc/profile.d/vmrun.sh
fi
if [ -z "$VMCREATEUSER" ]; then
    VMCREATEUSER="$VMUSERCREATE"
fi
#
# ----------------------------------------------------------
#

set -x

runShVer='run.sh 0.9.0 (Nov 03, 2014)'
buildAssessDriver="$VMINPUTDIR/build_assess_driver"

RUNOUT=$VMOUTPUTDIR/run.out
if [ -f "$RUNOUT" ]; then
    # restart of VM, just exit to allow for interactive debugging
    exit
fi

# set in run-params.conf
#
#SWAMP_USERNAME=
#SWAMP_USERID=
#SWAMP_PASSWORD=
#SWAMP_PASSWORD_IS_ENCRYPTED=
#USER_CONF=
#ROOT_PAYLOAD=
#USER_PAYLOAD=
#NOSHUTDOWN=
#NORUNPAYLOAD=

SLEEP_TIME=20
OPT_DIR=/opt

RUNPARAMSFILE=$VMINPUTDIR/run-params.conf

#
# for backwards compatibility, delete ----------------------
#
OLDRUNPARAMSFILE=$VMINPUTDIR/run-overrides.conf
if [ ! -f "$RUNPARAMSFILE" ] && [ -f "$OLDRUNPARAMSFILE" ]; then
    echo WARNING: using deprecated conf filename $OLDRUNPARAMSFILE instead of $RUNPARAMSFILE >> $RUNOUT 2>&1
    RUNPARAMSFILE="$OLDRUNPARAMSFILE"
fi
#
# ----------------------------------------------------------
#

if [ -f "$RUNPARAMSFILE" ]; then
    . "$RUNPARAMSFILE"
else
    echo "Error: '$RUNPARAMSFILE' not found, shutting down" >> $RUNOUT
    $VMSHUTDOWN >> $RUNOUT 2>&1
    exit 1
fi

#
# for backwards compatibility, delete ----------------------
#
if [ -z "$SWAMP_USERNAME" ] && [ -n "$MY_USERNAME" ]; then
    echo WARNING: using deprecated  MY_USERNAME instead of SWAMP_USERNAME >> $RUNOUT
	SWAMP_USERNAME="$MY_USERNAME"
fi
if [ -z "$SWAMP_USERID" ] && [ -n "$MY_USERID" ]; then
    echo WARNING: using deprecated  MY_USERID instead of SWAMP_USERID >> $RUNOUT
	SWAMP_USERID="$MY_USERID"
fi
if [ -z "$SWAMP_PASSWORD" ] && [ -n "$MY_PASSWORD" ]; then
    echo WARNING: using deprecated  MY_PASSWORD instead of SWAMP_PASSWORD >> $RUNOUT
	SWAMP_PASSWORD="$MY_PASSWORD"
fi
#
# ----------------------------------------------------------
#

if [ -z "$SWAMP_USERNAME" ]; then
    echo error: SWAMP_USERNAME not set, shutting down >> $RUNOUT
    $VMSHUTDOWN >> $RUNOUT 2>&1
    exit 1
fi

if [ -z "$SWAMP_USERID" ]; then
    echo error: SWAMP_USERID not set, shutting down >> $RUNOUT
    $VMSHUTDOWN >> $RUNOUT 2>&1
    exit 1
fi


echo "begin run.sh $runShVer" >> $RUNOUT
echo "========================== date" >> $RUNOUT
date >> $RUNOUT 2>&1
echo "========================== date -u" >> $RUNOUT
date -u >> $RUNOUT 2>&1
echo "========================== date +%s" >> $RUNOUT
date +%s >> $RUNOUT 2>&1
echo "========================== id" >> $RUNOUT
id >> $RUNOUT 2>&1
echo "========================== df" >> $RUNOUT
df >> $RUNOUT 2>&1
echo "========================== df -i" >> $RUNOUT
df -i >> $RUNOUT 2>&1
echo "========================== ifconfig" >> $RUNOUT
ifconfig >> $RUNOUT 2>&1
echo "========================== env" >> $RUNOUT
env >> $RUNOUT 2>&1
echo "========================== pwd" >> $RUNOUT
pwd >> $RUNOUT 2>&1
echo "========================== lsb_release -a" >> $RUNOUT
lsb_release -a >> $RUNOUT 2>&1
echo "========================== $buildAssessDriver --version" >> $RUNOUT
$buildAssessDriver --version >> $RUNOUT 2>&1
echo "==========================" >> $RUNOUT

if [ -z "$VMVERMAJOR" ]; then
    VMVERMAJOR=1
    VMVERMINOR=0

    if [ ! -f /etc/redhat-release ]; then
	echo "Found non-RedHat system, assuming debian" >> $RUNOUT
	VMUSERADD="$VMUSERADD -m"
	echo "   set VMUSERADD to '$VMUSERADD'" >> $RUNOUT
	echo "==========================" >> $RUNOUT
    fi


    echo "before $VMGROUPADD -g $SWAMP_USERID $SWAMP_USERNAME" >> $RUNOUT
    $VMGROUPADD -g $SWAMP_USERID $SWAMP_USERNAME >> $RUNOUT 2>&1

    echo "before $VMUSERADD -u $SWAMP_USERID -g $SWAMP_USERID $SWAMP_USERNAME" >> $RUNOUT
    $VMUSERADD -u $SWAMP_USERID -g $SWAMP_USERID $SWAMP_USERNAME >> $RUNOUT 2>&1
else
    echo "before $VMCREATEUSER -u $SWAMP_USERNAME -U $SWAMP_USERID -g $SWAMP_USERNAME -G $SWAMP_USERID" >> $RUNOUT
    $VMCREATEUSER -u $SWAMP_USERNAME -U $SWAMP_USERID -g $SWAMP_USERNAME -G $SWAMP_USERID >> $RUNOUT 2>&1

    # fix broken VMPLATNAME
    ARCH=`perl -e 'my $x=qx(uname -m);$x=~s/^i686$/32/;$x=~s/^x86_64/64/;print $x;'`
    VMOSVERSION=`echo $VMOSVERSION | perl -pe 's/^(18|19)$/$1.0/'`
    VMPLATNAME=${VMPLATNAME}_DO_NOT_USE_v2-$VMOSVERSION-$ARCH
fi

if [ -n "$SWAMP_PASSWORD" ]; then
    CHPASSWD=chpasswd
    if [ -n "$SWAMP_PASSWORD_IS_ENCRYPTED" ]; then
	CHPASSWD="$CHPASSWD -e"
    fi
    echo "before echo '$SWAMP_USERNAME:...' | $CHPASSWD" >> $RUNOUT
    echo "$SWAMP_USERNAME:$SWAMP_PASSWORD" | $CHPASSWD >> $RUNOUT 2>&1
else
    echo "SWAMP_PASSWORD not set, not setting password for $SWAMP_USERNAME" >> $RUNOUT
fi

echo "before add $SWAMP_USERNAME ALL = (ALL) ALL to /etc/sudoers" >> $RUNOUT
echo '' >> /etc/sudoers
echo "$SWAMP_USERNAME ALL = (ALL) NOPASSWD: ALL" >> /etc/sudoers

echo "before chsh -s /bin/bash $SWAMP_USERNAME" >> $RUNOUT
chsh -s /bin/bash $SWAMP_USERNAME >> $RUNOUT 2>&1

if [ ! -d "$OPT_DIR" ]; then
    echo "WARNING $OPT_DIR missing, creating" >> $RUNOUT
    echo "before mkdir -n 0755 $OPT_DIR" >> $RUNOUT
    mkdir -m 0755 "$OPT_DIR"
fi
userHomeDir=`eval echo ~$SWAMP_USERNAME`
swampBaseDir="$OPT_DIR/swamp-base"
echo "before ln -s '$userHomeDir' '$swampBaseDir'" >> $RUNOUT
ln -s "$userHomeDir" "$swampBaseDir" >> $RUNOUT 2>&1

envFile="$VMOUTPUTDIR/env.sh"
echo "before create $envFile" >> $RUNOUT
cat > "$envFile" <<EOF
export VMINPUTDIR='$VMINPUTDIR'
export VMOUTPUTDIR='$VMOUTPUTDIR'
export VMUSERADD='$VMUSERADD'
export VMGROUPADD='$VMGROUPADD'
export VMSHUTDOWN='$VMSHUTDOWN'
EOF

[ "$VMVERMAJOR" == 2 ] && cat >> "$envFile" <<EOF
export VMOSPACKAGEINSTALL='$VMOSPACKAGEINSTALL'
export VMCREATEUSER='$VMCREATEUSER'
export VMPLATNAME='$VMPLATNAME'
export VMOSVENDOR='$VMOSVENDOR'
export VMOSVERSION='$VMOSVERSION'
export VMPLATUPDATE='$VMPLATUPDATE'
export VMPLATUUID='$VMPLATUUID'
export VMOSFAMILY='$VMOSFAMILY'
export VMVERMAJOR='$VMVERMAJOR'
export VMVERMINOR='$VMVERMINOR'
EOF

[ "$VMVERMAJOR" == 1 ] && cat >> "$envFile" <<EOF
export VMUID='$VMUID'
export VMUSERNAME='$VMUSERNAME'
export VMGID='$VMGID'
export VMGROUPNAME='$VMGROUPNAME'
export VMCREATEVMUSER='$VMCREATEVMUSER'
#export VMVERMAJOR='$VMVERMAJOR'
#export VMVERMINOR='$VMVERMINOR'
EOF

echo "before chown -R $SWAMP_USERNAME.$SWAMP_USERNAME $VMINPUTDIR $VMOUTPUTDIR" >> $RUNOUT
chown -R $SWAMP_USERNAME.$SWAMP_USERNAME $VMINPUTDIR $VMOUTPUTDIR >> $RUNOUT 2>&1

if [ -n "$USER_CONF" ]; then
    echo "==========================" >> $RUNOUT
    echo "before su -c 'tar xzf $USER_CONF' - $SWAMP_USERNAME" >> $RUNOUT
    su -c "tar xzf $USER_CONF" - $SWAMP_USERNAME >> $RUNOUT 2>&1
fi

if [ -n "$ROOT_PAYLOAD" ]; then
    echo "==========================" >> $RUNOUT
    echo "before $ROOT_PAYLOAD" >> $RUNOUT
    $ROOT_PAYLOAD >> $RUNOUT 2>&1
fi

if [ -n "$NORUNPAYLOAD" ]; then
    echo "NORUNPAYLOAD set, exiting without running payload" >> $RUNOUT
    exit 0;
fi

echo "Sleeping $SLEEP_TIME seconds for network connectivity" >> $RUNOUT
sleep $SLEEP_TIME

echo "========================== ifconfig" >> $RUNOUT
ifconfig >> $RUNOUT 2>&1
echo "========================== date" >> $RUNOUT
date >> $RUNOUT 2>&1
echo "==========================" >> $RUNOUT

if [ -n "$USER_PAYLOAD" ]; then
    USER_PAYLOAD="$VMINPUTDIR/$USER_PAYLOAD"
    echo "before su -c \"$USER_PAYLOAD '$VMINPUTDIR' '$VMOUTPUTDIR' '$envFile'\" - $SWAMP_USERNAME" >> $RUNOUT 2>&1
    su -c "$USER_PAYLOAD '$VMINPUTDIR' '$VMOUTPUTDIR' '$envFile'" - $SWAMP_USERNAME >> $RUNOUT 2>&1
else
    baParams="--in-dir '$VMINPUTDIR' --out-dir '$VMOUTPUTDIR' --base-dir '$swampBaseDir'"
    if [ $VMVERMAJOR == 2 ]; then
	baParams="$baParams --plat-name '$VMPLATNAME'"
	baParams="$baParams --plat-uuid '$VMPLATUUID'"
	baParams="$baParams --os-pkg-install-cmd '$VMOSPACKAGEINSTALL'"
    fi

    echo "before su -c \"$buildAssessDriver $baParams\" - $SWAMP_USERNAME" >> $RUNOUT
    su -c "$buildAssessDriver $baParams" - $SWAMP_USERNAME >> $RUNOUT 2>&1
fi

echo "========================== df" >> $RUNOUT
df >> $RUNOUT 2>&1
echo "========================== df -i" >> $RUNOUT
df -i >> $RUNOUT 2>&1
echo "========================== ifconfig" >> $RUNOUT
ifconfig >> $RUNOUT 2>&1
echo "========================== date" >> $RUNOUT
date >> $RUNOUT 2>&1
echo "==========================" >> $RUNOUT
echo "end run.sh" >> $RUNOUT

if [ -n "$NOSHUTDOWN" ]; then
    echo "NOSHUTDOWN set, exiting without shutdown" >> $RUNOUT
    exit 0
fi

$VMSHUTDOWN >> $RUNOUT 2>&1
exit 1
