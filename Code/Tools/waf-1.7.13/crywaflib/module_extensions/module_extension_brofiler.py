# Copyright 2001-2016 Crytek GmbH / Crytek Group. All rights reserved.

import os
from waflib import Logs
from waflib.TaskGen import feature
from waflib.CryModuleExtension import module_extension
from waflib.Utils import run_once

@module_extension('brofiler')
def module_extensions_brofiler(ctx, kw, entry_prefix, platform, configuration):
	
	# CRYENGINE does not support Brofiler in release builds
	if configuration == 'release':
		return

	if platform not in ['win_x86', 'win_x64']:
		return

	kw[f'{entry_prefix}defines'] += [ 'USE_BROFILER' ]

	kw[f'{entry_prefix}includes'] += [
	    ctx.CreateRootRelativePath('Code/SDKs/Brofiler')
	]
	kw[f'{entry_prefix}libpath'] += [
	    ctx.CreateRootRelativePath('Code/SDKs/Brofiler')
	]

	profiler_name = 'ProfilerCore' + ('64' if platform == 'win_x64' else '32')
	kw[f'{entry_prefix}lib'] += [ profiler_name ]
	if platform != 'project_generator':
		kw[f'{entry_prefix}features'] += [ 'copy_brofiler_binaries' ]
		
@feature('copy_brofiler_binaries')
@run_once
def feature_copy_brofiler_binaries(self):
	bld 		= self.bld
	platform	= bld.env['PLATFORM']
	configuration = bld.env['CONFIGURATION']

	if platform  == 'project_generator':
		return

	if platform.startswith("win"):
		easyhook_name = 'EasyHook' + ('64' if platform == 'win_x64' else '32')
		brofilerCore_name = 'ProfilerCore' + ('64' if platform == 'win_x64' else '32')
		output_folder = bld.get_output_folders(platform, configuration)[0]
		brofiler_bin = bld.CreateRootRelativePath('Code/SDKs/brofiler') + os.sep

		self.create_task(
		    'copy_outputs',
		    bld.root.make_node(brofiler_bin + brofilerCore_name + '.dll'),
		    output_folder.make_node(f'{brofilerCore_name}.dll'),
		)
		if os.path.isfile(brofiler_bin + brofilerCore_name + '.pdb'):	
			self.create_task(
			    'copy_outputs',
			    bld.root.make_node(brofiler_bin + brofilerCore_name + '.pdb'),
			    output_folder.make_node(f'{brofilerCore_name}.pdb'),
			)		
				
			# self.create_task('copy_outputs', bld.root.make_node(brofiler_bin + easyhook_name + '.dll'), output_folder.make_node(easyhook_name + '.dll'))
			# if os.path.isfile(brofiler_bin + easyhook_name + '.pdb'):
				# self.create_task('copy_outputs', bld.root.make_node(brofiler_bin + easyhook_name + '.pdb'), output_folder.make_node(easyhook_name + '.pdb'))
	else:
		Logs.error(f'[ERROR] Brofiler is not supported for plaform {platform} by WAF.')
