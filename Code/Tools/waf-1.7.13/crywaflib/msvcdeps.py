#!/usr/bin/env python
# encoding: utf-8
# Copyright Garmin International or its subsidiaries, 2012-2013
# Christopher Bolte: Created a copy to easier adjustment to crytek specific changes

'''
Off-load dependency scanning from Python code to MSVC compiler

This tool is safe to load in any environment; it will only activate the
MSVC exploits when it finds that a particular taskgen uses MSVC to
compile.

Empirical testing shows about a 10% execution time savings from using
this tool as compared to c_preproc.

The technique of gutting scan() and pushing the dependency calculation
down to post_run() is cribbed from gccdeps.py.
'''

import os
import sys
import tempfile
import threading

from waflib import Context, Errors, Logs, Task, Utils
from waflib.Tools import c_preproc, c, cxx
from waflib.TaskGen import feature, before_method

lock = threading.Lock()
nodes = {} # Cache the path -> Node lookup

PREPROCESSOR_FLAG = '/showIncludes'
INCLUDE_PATTERN = 'Note: including file:'

# Extensible by outside tools
supported_compilers = ['msvc']

@feature('c', 'cxx', 'pch_msvc')
@before_method('process_source')
def apply_msvcdeps_flags(taskgen):
	if taskgen.env.CC_NAME not in supported_compilers:
		return

	# Figure out what casing conventions the user's shell used when
	# launching Waf
	(drive, _) = os.path.splitdrive(taskgen.bld.srcnode.abspath())
	taskgen.msvcdeps_drive_lowercase = drive == drive.lower()
	
	# Don't append show includes when in special single file mode
	if  taskgen.bld.is_option_true('show_preprocessed_file'):
		return
	if  taskgen.bld.is_option_true('show_disassembly'):
		return	
	
	for flag in ('CFLAGS', 'CXXFLAGS'):
		if taskgen.env.get_flat(flag).find(PREPROCESSOR_FLAG) < 0:
			taskgen.env.append_value(flag, PREPROCESSOR_FLAG)

def path_to_node(base_node, path, cached_nodes):
    # Take the base node and the path and return a node
    # Results are cached because searching the node tree is expensive
    # The following code is executed by threads, it is not safe, so a lock is needed...
    if getattr(path, '__hash__'):
        node_lookup_key = (base_node, path)
    else:
        # Not hashable, assume it is a list and join into a string
        node_lookup_key = (base_node, os.path.sep.join(path))
    try:
        lock.acquire()
        node = cached_nodes[node_lookup_key]
    except KeyError:
        node = base_node.find_resource(path)
        cached_nodes[node_lookup_key] = node
    finally:
        lock.release()
    return node

'''
Register a task subclass that has hooks for running our custom
dependency calculations rather than the C/C++ stock c_preproc
method.
'''
def wrap_compiled_task(classname):
    derived_class = type(classname, (Task.classes[classname],), {})

    def post_run(self):        
    	if self.env.CC_NAME not in supported_compilers:
    	    return super(derived_class, self).post_run()

    	if getattr(self, 'cached', None):
    	    return Task.Task.post_run(self)

    	bld = self.generator.bld
    	unresolved_names = []
    	resolved_nodes = []

    	lowercase = self.generator.msvcdeps_drive_lowercase
    	correct_case_path = bld.path.abspath()
    	correct_case_path_len = len(correct_case_path)
    	correct_case_path_norm = os.path.normcase(correct_case_path)

    	# Dynamically bind to the cache
    	try:
    	    cached_nodes = bld.cached_nodes
    	except AttributeError:
    	    cached_nodes = bld.cached_nodes = {}

    	for path in self.msvcdeps_paths:
    		node = None
    		if os.path.isabs(path):
    			# Force drive letter to match conventions of main source tree
    			drive, tail = os.path.splitdrive(path)

    			if os.path.normcase(path[:correct_case_path_len]) == correct_case_path_norm:
    				# Path is in the sandbox, force it to be correct.  MSVC sometimes returns a lowercase path.
    				path = correct_case_path + path[correct_case_path_len:]
    			elif lowercase and (drive != drive.lower()):
    				path = drive.lower() + tail
    			elif (not lowercase) and (drive != drive.upper()):
    			    path = drive.upper() + tail
    			node = path_to_node(bld.root, path, cached_nodes)
    		else:
    			base_node = bld.bldnode
    			# when calling find_resource, make sure the path does not begin by '..'
    			path = [k for k in Utils.split_path(path) if k and k != '.']
    			while path[0] == '..':
    			    path = path[1:]
    			    base_node = base_node.parent

    			node = path_to_node(base_node, path, cached_nodes)

    		if not node:
    			raise ValueError('could not find %r for %r' % (path, self))
    		if (not c_preproc.go_absolute and not node.is_child_of(bld.srcnode)
    		    and not node.is_child_of(bld.bldnode)):
    			# System library
    			Logs.debug('msvcdeps: Ignoring system include %r' % node)
    			continue

    		if id(node) == id(self.inputs[0]):
    		    # Self-dependency
    		    continue

    		resolved_nodes.append(node)

    	bld.node_deps[self.uid()] = resolved_nodes
    	bld.raw_deps[self.uid()] = unresolved_names

    	# Free memory (200KB for each file in CryEngine, without UberFiles, this accumulates to 1 GB)
    	del self.msvcdeps_paths

    	try:
    	    del self.cache_sig
    	except:
    	    pass

    	Task.Task.post_run(self)

    def scan(self):        
        if self.env.CC_NAME not in supported_compilers:
            return super(derived_class, self).scan()

        resolved_nodes = self.generator.bld.node_deps.get(self.uid(), [])
        unresolved_names = []
        return (resolved_nodes, unresolved_names)

    def sig_implicit_deps(self):        
        if self.env.CC_NAME not in supported_compilers:
            return super(derived_class, self).sig_implicit_deps()

        try:
            return Task.Task.sig_implicit_deps(self)
        except Errors.WafError:
            return Utils.SIG_NIL

    def exec_response_command(self, cmd, **kw):        
    	# exec_response_command() is only called from inside msvc.py anyway
    	assert self.env.CC_NAME in supported_compilers

    	try:
    		# The Visual Studio IDE adds an environment variable that causes
    		# the MS compiler to send its textual output directly to the
    		# debugging window rather than normal stdout/stderr.
    		#
    		# This is unrecoverably bad for this tool because it will cause
    		# all the dependency scanning to see an empty stdout stream and
    		# assume that the file being compiled uses no headers.
    		#
    		# See http://blogs.msdn.com/b/freik/archive/2006/04/05/569025.aspx
    		#
    		# Attempting to repair the situation by deleting the offending
    		# envvar at this point in tool execution will not be good enough--
    		# its presence poisons the 'waf configure' step earlier. We just
    		# want to put a sanity check here in order to help developers
    		# quickly diagnose the issue if an otherwise-good Waf tree
    		# is then executed inside the MSVS IDE.
								# Note seems something changed, and this env var cannot be found anymore
    		#assert 'VS_UNICODE_OUTPUT' not in kw['env']

    		tmp = None

    		            # This block duplicated from Waflib's msvc.py
    		if sys.platform.startswith('win') and isinstance(cmd, list) and len(' '.join(cmd)) >= 8192:
    			tmp_files_folder = self.generator.bld.get_bintemp_folder_node().make_node('TempFiles')
    			program = cmd[0]
    			cmd = [self.quote_response_command(x) for x in cmd]
    			(fd, tmp) = tempfile.mkstemp(dir=tmp_files_folder.abspath())
    			os.write(fd, '\r\n'.join(i.replace('\\', '\\\\') for i in cmd[1:]).encode())
    			os.close(fd)
    			cmd = [program, f'@{tmp}']
    		# ... end duplication

    		self.msvcdeps_paths = []

    		kw['env'] = kw.get('env', os.environ.copy())
    		kw['cwd'] = kw.get('cwd', os.getcwd())
    		kw['quiet'] = Context.STDOUT
    		kw['output'] = Context.STDOUT

    		out = []
    		try:                    
    		    raw_out = self.generator.bld.cmd_and_log(cmd, **kw)
    		    ret = 0
    		except Errors.WafError as e:
    		    try:
    		        # Get error output if failed compilation										
    		        raw_out = e.stdout
    		        ret = e.returncode
    		    except:										
    		        # Fallback (eg the compiler itself is not found)										
    		        raw_out = str(e)
    		        ret = -1

    		for line in raw_out.splitlines():
    			if line.startswith(INCLUDE_PATTERN):
    				inc_path = line[len(INCLUDE_PATTERN):].strip()
    				Logs.debug(f'msvcdeps: Regex matched {inc_path}')
    				self.msvcdeps_paths.append(inc_path)
    				if self.generator.bld.is_option_true('show_includes'):
    				    out.append(line)
    			else:
    				out.append(line)

    		show_output = any(' ' in i for i in out)
    		if show_output:
    			if self.generator.bld.logger:
    				self.generator.bld.logger.debug('out: %s' % '\n'.join(out))
    			else:
    				sys.stdout.write(os.linesep.join(out) + '\n')

    	finally:
    		if tmp:
    		    try:
    		        os.remove(tmp)
    		    except OSError:
    		        pass
						# Create custom error message for improved readibility
    	if ret != 0:
    		self.err_msg = '<++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++>\n'
    		self.err_msg += "Compilation failed - File: %r, Module: %r, Configuration: '%s|%s', error code %d\n" % (os.path.basename(self.outputs[0].abspath()), self.generator.target, self.generator.bld.env['PLATFORM'], self.generator.bld.env['CONFIGURATION'], ret )
    		self.err_msg += "\tInput Files:   '%s'\n" % ', '.join(i.abspath() for i in self.inputs)
    		self.err_msg += "\tOutput Files:  '%s'\n" % (', ').join(i.abspath() for i in self.outputs)
    		self.err_msg += "\tCommand:       '%s'\n" % ' '.join(self.last_cmd)
    		out_merged = ''.join('\t\t' + line + '\n' for line in out)
    		self.err_msg += "\tOutput:\n%s" % out_merged
    		self.err_msg += "<++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++>\n"

    	return ret

    def can_retrieve_cache(self):        
        # msvcdeps and netcaching are incompatible, so disable the cache
        if self.env.CC_NAME not in supported_compilers:
            return super(derived_class, self).can_retrieve_cache()
        self.nocache = True # Disable sending the file to the cache
        return False

    derived_class.post_run = post_run
    derived_class.scan = scan
    derived_class.sig_implicit_deps = sig_implicit_deps
    derived_class.exec_response_command = exec_response_command
    derived_class.can_retrieve_cache = can_retrieve_cache

for k in ('c', 'cxx', 'pch_msvc'):
    wrap_compiled_task(k)
