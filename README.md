# Nylas Sync Engine [![Build Status](https://travis-ci.org/nylas/sync-engine.svg?branch=master)](https://travis-ci.org/nylas/sync-engine)

The Nylas Sync Engine provides a RESTful API on top of a powerful email sync platform, making it easy to build apps on top of email. See the [full API documentation](https://www.nylas.com/docs/) for more details.

Need help? [Join our Slack channel ![Slack Invite Button](http://slack-invite.nylas.com/badge.svg)](http://slack-invite.nylas.com)


### Installation and Setup

1. Install the latest versions of [VirtualBox](https://www.virtualbox.org/wiki/Downloads) and [Install Vagrant](http://www.vagrantup.com/downloads.html).

2. `git clone https://github.com/nylas/sync-engine.git`

3. `cd sync-engine`

4. `vagrant up`

    Feel free to check out the `Vagrantfile` while this starts up. It creates a host-only network for the VM at `192.168.10.200`.

5. `vagrant ssh`

6. `cd /vagrant`

7. `NYLAS_ENV=dev bin/inbox-start`

And _voilà_! Auth an account via the commandline to start syncing:

    bin/inbox-auth ben.bitdiddle1861@gmail.com

The `inbox-auth` command will walk you through the process of obtaining an authorization token from Google or another service for syncing your mail. In the open-source version of the sync engine, your credentials are stored to the local MySQL database for simplicity. The open-source Nylas Sync Engine does not support Exchange, but the [hosted](https://www.nylas.com) version does.

The sync engine will automatically begin syncing your account with the underlying provider. The `inbox-sync` command allows you to manually stop or restart the sync by running `inbox-sync stop [YOUR_ACCOUNT]@example.com` or `inbox-sync start [YOUR_ACCOUNT]@example.com`. Note that an initial sync can take quite a while depending on how much mail you have.

### Digital Ocean Installation

To spin up a new Droplet with the sync engine installed on it, you'll need to modify the installation a little bit. The process below was successful in getting a DigitalOcean Ubuntu 14.04 Droplet to spin up a new DigitalOcean Ubuntu 12.04 Droplet.

**System Preparation**:

1. `sudo apt-get install dkms`

2. `sudo apt-get install dpkg-dev`

**Install VirtualBox**:

1. `sudo apt-key add oracle_vbox.asc`

2. `wget -q https://www.virtualbox.org/download/oracle_vbox.asc -O- | sudo apt-key add -`

3. `sudo apt-get update`

4. `sudo apt-get install virtualbox-5.1`
 
**Install Vagrant**:

1. `wget https://releases.hashicorp.com/vagrant/1.8.5/vagrant_1.8.5_x86_64.deb`

2. `dpkg -i vagrant_1.8.5_x86_64.deb`

**Reconfigure**:

1. `sudo apt-get install linux-headers-$(uname -r)`

2. `sudo dpkg-reconfigure virtualbox-5.1`
 
**Install Plugins for DigitalOcean and Vagrant**: 

1. `vagrant plugin install vagrant-digitalocean`

2. `vagrant plugin install vagrant-rekey-ssh`

**Generate a Key to Grant Access to the new Droplet**:

`ssh-keygen -t rsa`

**Include Root Certificates to Communicate with DigitalOcean**:

`nano ~/.bashrc`

Add this line to the end of your .bashrc file:

`export SSL_CERT_FILE=[YOUR_PATH_TO_YOUR_ROOT_CERTIFICATE]`

[Generate a DigitalOcean API Key](https://cloud.digitalocean.com/settings/applications) for your Vagrant configuration file.
 
[Follow steps 2 and 3 of the Installation and Setup steps above](https://github.com/nylas/sync-engine#installation-and-setup) to clone the sync engine to the directory of your choice.

Before running `vagrant up`, you will need to edit the Vagrantfile:

`sudo nano Vagrantfile`
 
Modify the Vagrantfile to customize your Droplet as desired. All elements of this sample should be included:
```
Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  config.vm.hostname = "[YOUR NEW DROPLET NAME]"

  config.vm.provider :digital_ocean do |provider, override|
    override.ssh.private_key_path = "[YOUR PATH TO NEW RSA KEY]"
    override.vm.box = "digital_ocean"

    provider.token = "[YOUR DO API TOKEN]"
    provider.image = "ubuntu-12-04-x64"
    provider.region = "nyc3"
    provider.size = "1gb"
    provider.ca_path = "[YOUR PATH TO YOUR ROOT CERTIFICATES]"
  end
```

At this point, you're ready to spin up a new droplet:

`vagrant up --provider=digital_ocean`
 
Once vagrant had spun up the new Droplet, run `vagrant ssh` to get into the new droplet and create a new non-root user and add it to the sudoers group. Make it the owner of the `/vagrant` directory that was created on the new Droplet. From there, you're set to explore the rest of the [Installation and Setup](https://github.com/nylas/sync-engine#installation-and-setup) instructions.

### Nylas API Service

The Nylas API service provides a REST API for interacting with your data. To start it in your development environment, run command below from the `/vagrant` folder within your VM:

```bash
$ bin/inbox-api
```

This will start the API Server on port 5555. At this point **You're now ready to make requests!** If you're using VirtualBox or VMWare fusion with Vagrant, port 5555 has already been forwarded to your host machine, so you can hit the API from your regular web browser.

You can get a list of all connected accounts by requesting `http://localhost:5555/accounts`. This endpoint requires no authentication.

For subsequent requests to retreive mail, contacts, and calendar data, your app should pass the `account_id` value from the previous step as the "username" parameter in HTTP Basic auth. For example:

```
curl --user 'ACCOUNT_ID_VALUE_HERE:' http://localhost:5555/threads
```

If you are using a web browser and would like to clear your cached HTTP Basic Auth values, simply visit http://localhost:5555/logout and click "Cancel".


Now you can start writing your own application on top of the Nylas API! For more information about the internals of the Nylas Sync Engine, see the <a href="https://nylas.com/docs/">Nylas API Documentation</a>.


## Production Support

We provide a fully managed and supported version of the Nylas sync engine for production apps. Read more at https://nylas.com

## Pull Requests

We'd love your help making Nylas better! Please sign-up for a [developer account](https://nylas.com/register) for project updates and the latest news. Feel free to create issues or pull requests to start discussions.

We require all authors sign our [Contributor License Agreement](https://www.nylas.com/cla.html) when submitting pull requests. (It's similar to other projects, like NodeJS or Meteor.)

## Security

For the sake of simplicity and setup speed, the development VM does not include any authentication or permission. For developing with sensitive data, we encourage developers to add their own protection, such as only running Nylas on a local machine or behind a controlled firewall.
Note that passwords and OAuth tokens are stored unencrypted in the local MySQL data store on disk. This is intentional, for the same reason as above.

## License

This code is free software, licensed under the The GNU Affero General Public License (AGPL). See the `LICENSE` file for more details.
