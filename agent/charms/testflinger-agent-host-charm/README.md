# Overview

This charm provides the base system for a host system that will be used for
testflinger device agents. It installs the base dependencies and provides a
target for deploying the "testflinger-agent" along with
"testflinger-device-connector" on top of. Additionally, it copies the scripts
in `src/tf-cmd-scripts/` to the host system. The scripts would be used by the
testflinger-agent to trigger the testflinger-device-connector at each phase.

# Building
To build this charm, first install charmcraft (`sudo snap install --classic
charmcraft`) then run `charmcraft pack`

# Configuration
Supported options for this charm are:

  - ssh-priv-key:
      base64 encoded ssh private keyfile
  - ssh-pub-key:
      base64 encoded ssh public keyfile

To keep the tf-cmd-scripts files up-to-date, run `juju upgrade-charm
{testflinger-agent-host-application}`.