Vagrant.configure("2") do |config|
  config.vm.define "moerderspiel" do |thevm|
    thevm.vm.box = "debian/bookworm64"
    thevm.vm.hostname = "moerderspiel"
    thevm.vm.provision "shell", inline: 'apt-get update && apt-get upgrade --yes'
    thevm.vm.synced_folder '.', '/vagrant', type: '9p'
  end
end

