from katana.unit import BaseUnit
from collections import Counter
import sys
from io import StringIO
import argparse
from pwn import *
import subprocess
from katana.units import raw
from katana import utilities
import os
from katana.units import NotApplicable
from katana import units

DEPENDENCIES = [ 'strings' ]

class Unit(BaseUnit):

	PRIORITY = 25
	ARGUMENTS = [
		{ 'name': 'strings_length',
		  'type': int,
		  'default': 4,
		  'required': False,
		  'help': "minimum length of strings to return" 
		}
	]

	@classmethod
	def add_arguments(cls, katana, parser):
		parser.add_argument('--strings-length', '-sl', type=int,
				help="minimum length of strings to return", default=4)

	def __init__(self, katana, target):
		super(Unit, self).__init__(katana, target)

		if not self.target.is_file:
			raise NotApplicable("not a file")

	def evaluate(self, katana, case):
		
		# Run the process.
		p = subprocess.Popen(['strings', self.target.path, '-n', str(katana.config['strings_length'])], 
			stdout = subprocess.PIPE, stderr=subprocess.PIPE )

		lines = []
		for line in p.stdout:
			katana.locate_flags(self, line)
			lines.append(line)

		for line in lines:
			katana.recurse(self, line)

		# Look for flags, if we found them...
#		response = utilities.process_output(p)
#		if response:
#			if 'stdout' in response:
#				
#				# If we see anything interesting in here... scan it again!
#				for line in response['stdout']:
#					katana.locate_flags(self, line)
#					katana.recurse(self, line)
#
#			if 'stderr' in response:
#				katana.locate_flags(self, str(response['stderr']))

#			katana.add_results(self, response)
			