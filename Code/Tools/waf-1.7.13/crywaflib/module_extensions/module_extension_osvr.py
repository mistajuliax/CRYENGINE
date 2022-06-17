# Copyright 2001-2015 Crytek GmbH. All rights reserved.

import os
from waflib import Logs, Utils
from waflib.TaskGen import feature
from waflib.CryModuleExtension import module_extension
from waflib.Utils import run_once

@Utils.memoize
def check_path_exists(path):
	if os.path.isdir(path):
		return True
	else:
		Logs.warn(
		    f'[WARNING] {path} not found, this feature is excluded from this build.')
	return False

@module_extension('osvr')
def module_extensions_osvr(ctx, kw, entry_prefix, platform, configuration):
	if platform  == 'project_generator':
		return

	if not check_path_exists(ctx.CreateRootRelativePath('Code/SDKs/OSVR-Core')):
		return

	if not check_path_exists(ctx.CreateRootRelativePath('Code/SDKs/OSVR-RenderManager')):
		return

	if platform == 'win_x64':
		kw[f'{entry_prefix}includes'] += [
		    ctx.CreateRootRelativePath('Code/SDKs/OSVR-Core/include'),
		    ctx.CreateRootRelativePath('Code/SDKs/OSVR-RenderManager/include'),
		]
		kw[f'{entry_prefix}defines'] += [ 'INCLUDE_OSVR_SDK' ]
		kw[f'{entry_prefix}libpath'] += [
		    ctx.CreateRootRelativePath('Code/SDKs/OSVR-Core/lib/'),
		    ctx.CreateRootRelativePath('Code/SDKs/OSVR-RenderManager/lib/'),
		]
		kw[f'{entry_prefix}lib'] += [ 'osvrClientKit', 'osvrRenderManager' ]
		kw[f'{entry_prefix}features'] += [ 'feature_copy_osvr_binaries' ]

@feature('feature_copy_osvr_binaries')
@run_once
def feature_copy_osvr_binaries(self):
	bld 			= self.bld
	platform	= bld.env['PLATFORM']
	configuration = bld.env['CONFIGURATION']

	if platform  == 'project_generator':
		return

	files_to_copy_from_osvr_sdk = ['osvrClient.dll', 'osvrClientKit.dll', 'osvrCommon.dll', 'osvrUtil.dll']
	files_to_copy_from_osvr_rendermanager = ['osvrRenderManager.dll', 'glew32.dll', 'SDL2.dll']
	if platform not in ['win_x64']:
		Logs.error(f'[ERROR] Osvr is not supported for plaform {platform} by WAF')

	for file in files_to_copy_from_osvr_sdk:
		src_path = bld.CreateRootRelativePath(f'Code/SDKs/OSVR-Core/bin/{file}')
		output_folder = bld.get_output_folders(platform, configuration)[0]
		if os.path.isfile(src_path):
			self.create_task('copy_outputs', bld.root.make_node(src_path), output_folder.make_node(file))
		else:
			Logs.warn(f'[WARNING] Osvr DLL not found at: {src_path}')

	for file in files_to_copy_from_osvr_rendermanager:
		src_path = bld.CreateRootRelativePath(f'Code/SDKs/OSVR-RenderManager/{file}')
		output_folder = bld.get_output_folders(platform, configuration)[0]
		if os.path.isfile(src_path):
			self.create_task('copy_outputs', bld.root.make_node(src_path), output_folder.make_node(file))
		else:
			Logs.warn(f'[WARNING] Osvr-RenderManager DLL not found at: {src_path}')