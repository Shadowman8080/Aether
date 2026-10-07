import importlib.machinery
import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch
loader=importlib.machinery.SourceFileLoader('firewall',str(Path(__file__).with_name('aether-firewall')))
spec=importlib.util.spec_from_loader(loader.name,loader);fw=importlib.util.module_from_spec(spec);loader.exec_module(fw)
HOME='4c49464d-0000-4000-8000-111111111111';PUBLIC='4c49464d-0000-4000-8000-222222222222'
class NetworkProfileTests(unittest.TestCase):
 def config(self):return {'tcp':[],'udp':[],'phone_private_lan':True,'trusted_connections':[HOME],'home_tcp':[8443]}
 def test_untrusted_network_has_no_phone_or_home_exception(self):
  text=fw.rules(self.config(),{PUBLIC:'ens33'});self.assertNotIn('1714-1764',text);self.assertNotIn('8443',text)
 def test_home_rules_bind_to_interface(self):
  text=fw.rules(self.config(),{HOME:'ens33',PUBLIC:'ens34'});self.assertIn('iifname "ens33" tcp dport { 8443 }',text);self.assertNotIn('ens34',text)
 def test_legacy_phone_optin_is_not_network_trust(self):
  self.assertNotIn('1714-1764',fw.rules({'tcp':[],'udp':[],'phone_private_lan':True},{}))
 def test_nm_failure_closes_scoped_exceptions(self):
  with patch.object(fw,'active_connections',side_effect=subprocess.TimeoutExpired('nmcli',10)):
   self.assertNotIn('1714-1764',fw.rules(self.config()))
 def test_interface_injection_is_rejected(self):
  self.assertNotIn('1714-1764',fw.rules(self.config(),{HOME:'eth0" accept;'}))
 def test_uuid_validation(self):
  c=self.config();c['trusted_connections']=['--help']
  with self.assertRaises(ValueError):fw.validate(c)
 def test_global_port_behavior_is_explicitly_preserved(self):
  c=self.config();c['tcp']=[443];self.assertIn('tcp dport { 443 } counter accept',fw.rules(c,{}))
 def test_no_other_firewall_table_is_flushed(self):
  text=fw.rules(self.config(),{});self.assertNotIn('flush ruleset',text);self.assertIn('flush table inet aether_filter',text)
if __name__=='__main__':unittest.main()
