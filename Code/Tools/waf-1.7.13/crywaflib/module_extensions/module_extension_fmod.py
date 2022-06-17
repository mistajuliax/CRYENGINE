# Copyright 2001-2016 Crytek GmbH / Crytek Group. All rights reserved.

import os
from waflib import Logs
from waflib.TaskGen import feature
from waflib.CryModuleExtension import module_extension
from waflib.Utils import run_once

@module_extension('audio_fmod')
def module_extensions_audio_fmod(ctx, kw, entry_prefix, platform, configuration):	
	if not platform.startswith('win'):
		return

	if platform != 'project_generator':
		kw[f'{entry_prefix}features'] += [ 'copy_audio_fmod_binaries' ]

@feature('copy_audio_fmod_binaries')
@run_once
def feature_copy_audio_fmod_binaries(self):
	bld = self.bld
	platform = bld.env['PLATFORM']
	configuration = bld.env['CONFIGURATION']

	if platform == 'project_generator':
		return

	if platform not in ['win_x86', 'win_x64']:
		Logs.error(
		    f'[ERROR] Fmod audio is not supported for plaform {platform} by WAF')

	bin1_name = 'fmod64.dll'
	bin2_name = 'fmodstudio64.dll'
	src1_path = bld.CreateRootRelativePath(
	    f'Code/SDKs/audio/fmod/windows/api/lowlevel/lib/{bin1_name}')
	src2_path = bld.CreateRootRelativePath(
	    f'Code/SDKs/audio/fmod/windows/api/studio/lib/{bin2_name}')

	output_folder = bld.get_output_folders(platform, configuration)[0]

	if os.path.isfile(src1_path):
		self.create_task('copy_outputs', bld.root.make_node(src1_path), output_folder.make_node(bin1_name))
	else:
		Logs.warn(f'[WARNING] Fmod audio DLL not found at: {src1_path}')

	if os.path.isfile(src2_path):
		self.create_task('copy_outputs', bld.root.make_node(src2_path), output_folder.make_node(bin2_name))
	else:
		Logs.warn(f'[WARNING] Fmod audio DLL not found at: {src2_path}')
