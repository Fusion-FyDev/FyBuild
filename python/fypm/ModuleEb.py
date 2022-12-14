# from FyDev.python.tests.test_basic import module
# from FyBuild.python.fypm.writefile import generate_yaml_doc_ruamel
import collections
import os
import sys
# sys.path.append('/scratch/liuxj/FYDEV-Workspace/SpDB/python')
import pathlib
import shlex
import subprocess
import signal
import traceback
import uuid
import re
from pathlib import Path, PurePath,PurePosixPath
# import yaml
import time
import linecache
# from ruamel.yaml import YAML
from ruamel import yaml

from spdm.util.logger import logger

# sys.path.append('/scratch/liuxj/FYDEV-Workspace/FyBuild/python')
from spdm.flow.ModuleRepository import ModuleRepository
import pprint
from fypm.StandardModule import  StandardModule
import  fypm.EasyBuildPa as bs

# import module tool  from EasyBuild 
from easybuild.tools.filetools import remove_dir
from easybuild.tools.modules import get_software_root_env_var_name, modules_tool
from easybuild.tools.options import set_up_configuration
from easybuild.tools.run import run_cmd

#  import easyconfig  from EasyBuild  framework
from easybuild.framework.easyconfig.tools import det_easyconfig_paths, parse_easyconfigs,skip_available

# import robot  from EasyBuild  tools (-Dr)
from easybuild.tools.robot import check_conflicts, dry_run, missing_deps, resolve_dependencies, search_easyconfigs

#  import easyblock  from EasyBuild  framework
from easybuild.framework.easyblock import EasyBlock, get_easyblock_instance

#  import easybuild.main and testng   from EasyBuild  framework

from easybuild.main import build_and_install_software
from easybuild.tools.testing import create_test_report, overall_test_report, regtest, session_state
# for log or error
from easybuild.tools.build_log import EasyBuildError, print_error, print_msg, stop_logging
# for hook 
from easybuild.tools.hooks import START, END, load_hooks, run_hook



class ModuleEb(ModuleRepository):
    '''Module wrapper.

    This class represents internally a module. Concrete module system
    implementation should deal only with that.
    the init will provide the name ,version ,tag and fullname .
    if the version is null ,I dont know what you want .
    If the tag is null ,I can read the default tag from configure,yaml \
        which by def load_configure() in class ModuleRepository .
    '''

    def __init__(self, name, version,tag,collection=False,depend_args=[],install_args=[],path=None,repo_name=None, repo_tag=None,*args,**kwargs):

        super().__init__(repo_name=None, repo_tag=None,*args ,**kwargs)
        
        name = name.strip()
        if not name:
            raise ValueError('module name cannot be empty,I dont know what you want')
        if not isinstance(name, str):
            raise TypeError('module name not a string')

        version = version.strip()

        if not isinstance(version, str):
            raise TypeError('module version not a string')

        tag = tag.strip()  
        if not isinstance(tag, str):
            raise TypeError('module tag not a string')            

        # first check the contition ,get the all value
        if not version:
        # for version=NULL , if need to give the error and exit????
            try:
                logger.warning(f"the version is empity,I dont know what you want "
                                f"you can use fetch to check which module is installed")
                self._name = name
                self._version = " "
                self._tag = " "
                self._fullname = name
            except:
                raise ValueError(f"the version is empity,I dont know what you want ")
        elif tag :
            try :
                self._name = name
                self._version = version
                self._tag = tag
                self._modulename = '-'.join((self._name, self._version))
                self._modulefullname = '-'.join((self._name, self._version,self._tag))
                self._fullname = '-'.join(('/'.join((self._name, self._version)),self._tag))
            
            except :
                raise ValueError('I cannot get fullname ,I dont know what you want')            
        else :
            try:
                """
                default_tag = self.load_configure(self),here is the interface with the class ModuleRepository
                which get the default tag from the configure file .
                """
                # default_module = self.__init__( name, version,tag,collection=False, path=None,repo_name=None, repo_tag=None,*args,**kwargs)
                # path="/scratch/liuxj/FYDEV-Workspace/FyDev/python/tests/data/FuYun/configure.yaml"
                self.load_configure(path)
                default_tag = self._conf.get("default_toolchain")
                logger.debug(f"the default_tag name from the default-configure  is '{default_tag}'")
                # default_tag = 'foss-2020a'
                self._name = name
                self._version = version
                self._tag = default_tag
                self._modulename = '-'.join((self._name, self._version))
                self._modulefullname = '-'.join((self._name, self._version,self._tag))
                self._fullname = '-'.join(('/'.join((self._name, self._version)),self._tag))
                # self.eb_options = eb_options
            except :
                raise ValueError('I cannot get name ,I dont know what you want')            
                
        self._path = path
        self._ebfilename = '-'.join(self._fullname.split('/'))

        self.install_args= install_args
        self.depend_args= depend_args

    @property
    def name(self):
        return self._name

    @property
    def version(self):
        return self._version

    @property
    def tag(self):
        return self._tag

    @property
    def path(self):
        return self._path

    @property
    def modulename(self):
        return self._modulename


    @property
    def modulefullname(self):
        return self._modulefullname

    @property
    def fullname(self):
        return self._fullname

    @property
    def ebfilename(self):
        return self._ebfilename

  

    def __hash__(self):
        # Here we hash only over the name of the module, because foo/1.2 and
        # simply foo compare equal. In case of hash conflicts (e.g., foo/1.2
        # and foo/1.3), the equality operator will resolve it.
        return hash(self.name)

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented

        if self.path != other.path:
            return False

        if not self.version or not other.version:
            return self.name == other.name
        else:
            return self.name == other.name and self.version == other.version

    def __repr__(self):
        return self.fullname

    def __str__(self):
        return self.fullname
    
    def search_fymodule(self,*args,**kwargs):
        """Find fymodule in  /gpfs/fuyun/ModuleRepository/name/ .If the file is exsit,the package is exsit';not,you need to install it"""
        path=self.path
        logger.debug(f'the path dir  is {path}')
        self.load_configure(path)
        software_path = self._conf.get("MoResp_dir")
        flag = 0
        name = self.name
        modulename = self.modulefullname
        # software_path = "/gpfs/fuyun/fy_modules/physics/" 
        templefilename = modulename+'.yaml'
        logger.debug(f'the fy-modulename   is {templefilename}')
        fymodule_path = software_path+'/'+name
        logger.debug(f'the fymodule_path   is {fymodule_path}')
        if Path(fymodule_path).exists() :
            if  Path(Path(Path(fymodule_path).joinpath(templefilename))).is_file() :
                flag +=1
                return flag,Path(Path(Path(fymodule_path).joinpath(templefilename)))
            else :
                raise FileNotFoundError(f"the {templefilename} file doesn't exist in the directpry {fymodule_path}.")
        else:
            raise FileNotFoundError(f"the {fymodule_path} path doesn't exist.")
   
   
    def list_avail_pa(self,*args,**kwargs):
        fullname = self.fullname
        logger.debug(f'the fy-fullname   is {fullname}')
        if not isinstance(fullname, str):
             raise TypeError('module name not a string')
        opts, cfg_settings = set_up_configuration(args=[], silent=True)
        mod_tool = modules_tool()
        list_avail_modules = mod_tool.available(fullname)
        logger.debug(f'the fy-list_avail_modules   is {list_avail_modules}')
        if len(list_avail_modules) :
            return list_avail_modules
        else:
           raise KeyError(f"the {fullname} is not installed,you need connect to the manager  to install it ! .")


    def checkpa(self,*args,**kwargs):
        # to check the modulename which will be install is installed or not 
        fullname = self.fullname
        if not isinstance(fullname, str):
            raise TypeError('module name not a string')
        opts, cfg_settings = set_up_configuration(args=[], silent=True)
        mod_tool = modules_tool()
        flag = 0
        if fullname.find("/") != -1:
            avail_eb_modules = mod_tool.available(fullname)
            logger.debug(f"the output of installed module is {len(avail_eb_modules)}")
            if len(avail_eb_modules) :
                flag +=1
            # logger.log(f"the output of installed module is {avail_eb_modules}")
                return flag,avail_eb_modules
            else:
                logger.debug(f'the {fullname} is not installed.')
                return flag,None
                # raise TypeError(f"the {fullname} is not installed .") #delete by 2021.11.1
                # self.listpa(fullname,max_list = True)
        else:
            raise KeyError(f"the {fullname} is incomplete.")

    def search_ebfiles(self,*args,**kwargs):
        """Find ebfiles in  /gpfs/fuyun/EbfilesRespository/name/ .If the file is exsit,you can use it ';not,you need to try-toolchain to use  it"""
        flag = 0
        name = self.name
        modulename = self.modulefullname
        opts, cfg_settings = set_up_configuration(args=[], silent=True)
        mod_tool = modules_tool()
        # software_path = "/gpfs/fuyun/fy_modules/physics/" 
        ebfilename = modulename+'.eb'
        logger.debug(f'the fy-ebfilename   is {ebfilename}')
        ebfile_path = det_easyconfig_paths([ebfilename])[0]
        if len(ebfile_path) :
            flag +=1
            # logger.log(f"the output of installed module is {avail_eb_modules}")
            return ebfile_path
        else:
            logger.log(f"the output of installed module is null")
            return " "
            # delete at 2021-10-07
        #    ## add the try-funtction to yeild ebfiles . 
        #     raise KeyError(f"the {ebfile_path} is not not exsit .")
        #     # self.listpa(fullname,max_list = True)

    def listdepend(self,*args,**kwargs):
        """ TO check the ebfile is ok or not "-Dr" """
        args_list=[]
        extend_args=self.depend_args
        if len(extend_args):
            for i in range(0,len(extend_args)):
                args_list.append(extend_args[i])
        modulename = self.modulefullname
        ebfilename = modulename+'.eb'
        opts, cfg_settings = set_up_configuration(args=args_list, silent=True)
        logger.debug(f'the cfg_settings  is {cfg_settings}') 
        (build_specs, _log, logfile, robot_path, search_query, eb_tmpdir, try_to_generate, tweaked_ecs_paths,*other) = cfg_settings
        mod_tool = modules_tool()
        ebfile_path = det_easyconfig_paths([ebfilename])[0]
        ec_dicts, _ = parse_easyconfigs([(ebfile_path, False)])
        txt = dry_run(ec_dicts, mod_tool, short=False)
        deplist=txt.split('\n')
        if len(deplist) <2 :
            raise KeyError(f"the {ebfile_path} is unavailable .") 

        dependcommand = ['eb -Dr']
        dependcommand.extend(args_list)
        dependcommand.extend(robot_path)
        dependcommandline = ' '.join(dependcommand)

        return dependcommandline,deplist
        remove_dir(opts.tmpdir)

    def fetchsources(self,dry_run=False,*args,**kwargs):
        """ To get the sources ;if dry_run = False ,just get the easycofig itself ;if dry_run=Ture,get all sources in dependence"""
        eb_sources=[]
        modulename = self.modulefullname
        ebfilename = modulename+'.eb'
        opts, cfg_settings = set_up_configuration(args=[], silent=True)
        mod_tool = modules_tool()
        logger.debug(f'the cfg_settings  is {cfg_settings}') 
        (build_specs, _log, logfile, robot_path, search_query, eb_tmpdir, try_to_generate, tweaked_ecs_paths,*other) = cfg_settings
        ebfile_path = det_easyconfig_paths([ebfilename])[0]
        ec_dicts, _ = parse_easyconfigs([(ebfile_path, False)])
        print(ec_dicts)
        # print(ec_dicts['ec']['name'])
        # print(ec_dicts['ec']['name'])
        if (dry_run == False):
            eb = get_easyblock_instance(ec_dicts[0])
            eb.fetch_sources()
            eb_sources=eb.src
        else:
            ordered_ecs = resolve_dependencies(ec_dicts, mod_tool,retain_all_deps=True)
            # print(ordered_ecs)
            
            print(type(ordered_ecs))
            print(len(ordered_ecs))
            for ec in  ordered_ecs:
                print(ec)
                eb = get_easyblock_instance(ec)
                print(dir(eb))
                eb.fetch_sources()
                eb_sources.append(eb.src[0])
        return eb_sources
        remove_dir(opts.tmpdir)

    def installpa(self,*args,**kwargs):
        args_list=[]
        extend_args=self.install_args
        if len(extend_args):
            for i in range(0,len(extend_args)):
                args_list.append(extend_args[i])
        opts,cfg_settings =set_up_configuration(args=args_list, silent=True)

        mod_tool = modules_tool()
        logger.debug(f'the cfg_settings  is {cfg_settings}') 
        # if len(cfg_settings)>8: 
        #     (build_specs, _log, logfile, robot_path, search_query, eb_tmpdir, try_to_generate, tweaked_ecs_paths,other) = cfg_settings
        # else:
        #     (build_specs, _log, logfile, robot_path, search_query, eb_tmpdir, try_to_generate, tweaked_ecs_paths) = cfg_settings
        (build_specs, _log, logfile, robot_path, search_query, eb_tmpdir, try_to_generate, tweaked_ecs_paths,*other) = cfg_settings
        modulename = self.modulefullname
        ebfilename = modulename+'.eb'

        hooks = load_hooks(opts.options.hooks)
        run_hook(START, hooks)
        ebfile_path = det_easyconfig_paths([ebfilename])[0]
        easyconfigs, _ = parse_easyconfigs([(ebfile_path, False)])
        init_session_state = session_state()
        # update session state
        eb_config = opts.generate_cmd_line(add_default=True)
        modlist = mod_tool.list()  # build options must be initialized first before 'module list' works
        init_session_state.update({'easybuild_configuration': eb_config})
        init_session_state.update({'module_list': modlist})
        forced = opts.options.force or opts.options.rebuild
        dry_run_mode = opts.options.dry_run or opts.options.dry_run_short or opts.options.missing_modules

        # skip modules that are already installed unless forced, or unless an option is used that warrants not skipping
        if not (forced or dry_run_mode or opts.options.extended_dry_run or opts.options.inject_checksums):
            retained_ecs = skip_available(easyconfigs, mod_tool)
            for skipped_ec in [ec for ec in easyconfigs if ec not in retained_ecs]:
                print_msg("%s is already installed (module found), skipping" % skipped_ec['full_mod_name'])
            easyconfigs = retained_ecs

        if len(easyconfigs) > 0:
            # resolve dependencies if robot is enabled, except in dry run mode
            # one exception: deps *are* resolved with --new-pr or --update-pr when dry run mode is enabled
            if opts.options.robot and (not dry_run_mode):
                print_msg("resolving dependencies ...", log=_log)
                ordered_ecs = resolve_dependencies(easyconfigs, mod_tool)
            else:
                ordered_ecs = easyconfigs
        # elif opts.options.pr_options:
        #     ordered_ecs = None
        else:
            print_msg("No easyconfigs left to be built.", log=_log)
            ordered_ecs = []
        if len(ordered_ecs) > 0:
            ecs_with_res=build_and_install_software(ordered_ecs, init_session_state, exit_on_failure=True)
        if (self.checkpa(*args,**kwargs)[0] ==1):
            modulename=self.checkpa(*args,**kwargs)[1][0]
            # ????????????????????????????????????????????????
            env_var_name = get_software_root_env_var_name(self.name)
            mod_tool.load([modulename])
            print("Current $%s value: %s" % (env_var_name, os.getenv(env_var_name, '(no set)')))
            ebfilepath=os.getenv(env_var_name, '(no set)')+'/easybuild/'+ebfilename
            moduleinstalldir=os.getenv(env_var_name, '(no set)')+'/easybuild/'
            eb_command =[]
            str = "test_report.md"
            for filepath in os.listdir(moduleinstalldir):
                if str in filepath:
                    mdfile=moduleinstalldir+filepath
            with open(mdfile) as f :
                key = "* command line:"
                i=0
                for line in f.readlines()[:100]:
                    i+=1
                    if key in line:
                        break
            with open(mdfile) as f :
                key2 = "* full configuration (includes defaults):"
                j=i
                for line in f.readlines()[i:100]:
                    j+=1
                    if key2 in line:
                        break
            for k in range(i+1,j):
                the_line = linecache.getline(mdfile, k)
                eb_command.append(the_line)
            print("the eb_command is: ", eb_command)
            eb_commandline=eb_command[1].strip()
            if len(eb_commandline) >0:
                command=[]
                command.extend([eb_commandline])
                command.extend(args_list)
                command.extend(robot_path)
                command.extend([ebfile_path])
                eb_commandline = ' '.join(command)
                # eb_commandline = command
        else:
           ## add the try-funtction to yeild ebfiles . 
            raise KeyError(f"the package {modulename} is not installed .")
        #  eb-command??????????????????,?????????????????????????????????????????????conmand-line????????????????????????command-line

            #???????????????????????????????????????????????????deploy??????????????????????????????
            # mod_tool.load(modulename)
        # ?????????????????????????????????????????????eb???????????????cmd??????:eb ebfilename 
        #  
        # return ordered_ecs
        return ebfilepath,eb_commandline  
        remove_dir(opts.tmpdir)     
        run_hook(END, hooks)
    
    def search_fymodule_file(self,*args,**kwargs):
        """Find templefile match  packages  name (in /gpfs/fuyun/fy_modules and other  /gpfs/fuyun/fy_modules/gemray)."""
        path=self.path
        logger.debug(f'the path dir  is {path}')
        self.load_configure(path)
        software_path = self._conf.get("MoResp_dir")
        templepath  = None
        flag = 0
        name = self.name
        # software_path = "/gpfs/fuyun/fy_modules/physics/" 
        # templefilename = 
        # templefilename = 
        logger.debug(f'the MoResp_dir dir  is {software_path}')
        templefilename = self.modulename +'-'+ self.tag+'.yaml'
        templefilename_sub = self.version +'-'+ self.tag+'.yaml'
        logger.debug(f'the templefilename   is {templefilename}')
        logger.debug(f'the templefilename_sub  is {templefilename_sub}')       

        if Path(software_path).exists() :
            # templepath = Path(tmplefile).parent
            print("ok1")
            if  Path(Path(Path(software_path).joinpath(templefilename))).is_file() :
                print("ok2")
                flag +=1
                # search = Path(Path(Path(software_path).joinpath(name,templefilename)))
                # print(search)
                return flag,Path(Path(Path(software_path).joinpath(templefilename))),templefilename
            elif Path(software_path+'/'+self.name).exists() :
                print("ok3")
                if Path(Path(Path(software_path).joinpath(name,templefilename_sub))).is_file()  :
                    print("ok4")
                # search = Path(Path(Path(software_path).joinpath(name,templefilename)))

                # print(search)
                    flag +=1
                    return flag,Path(Path(Path(software_path).joinpath(name,templefilename_sub)))
                else :
                    print("ok5")

                    return flag,Path(Path(software_path+'/'+self.name)),templefilename_sub
            else :
                print("ok6")
                Path(software_path+'/'+self.name).mkdir()
                return flag,Path(software_path+'/'+self.name),templefilename_sub
        else:
            print("ok7")
            Path(software_path).mkdir()
            return flag,Path(software_path)
        #     raise  RuntimeError('could fount the templefile ,please gime me it  ') 
                
    def search_tmple_file(self,MoResp_dir=None,*args,**kwargs):
        """Find templefile match  packages  name (in /gpfs/fuyun/fy_modules and other  /gpfs/fuyun/fy_modules/gemray)."""
        path=self.path
        logger.debug(f'the path dir  is {path}')
        self.load_configure(path)
        if MoResp_dir == None:
            software_path = self._conf.get("MoResp_dir")
        else:
            software_path = MoResp_dir
        templepath  = None
        flag = 0
        name = self.name
        # software_path = "/gpfs/fuyun/fy_modules/physics/" 
        templefilename = "temple.yaml"
        # templefilename = 
        logger.debug(f'the MoResp_dir dir  is {software_path}')

        if Path(software_path).exists() :
            # templepath = Path(tmplefile).parent
            if  Path(Path(Path(software_path).joinpath(templefilename))).is_file() :
                flag +=1
                # search = Path(Path(Path(software_path).joinpath(name,templefilename)))
                # print(search)
                return flag,Path(Path(Path(software_path).joinpath(templefilename)))
            elif Path(Path(Path(software_path).joinpath(name,templefilename))).is_file()  :
                # search = Path(Path(Path(software_path).joinpath(name,templefilename)))

                # print(search)
                flag +=1
                return flag,Path(Path(Path(software_path).joinpath(name,templefilename)))
            else :
                return flag,Path(software_path)
        else:
            return flag,None
        #     raise  RuntimeError('could fount the templefile ,please gime me it  ') 
        
    def generate_yaml_doc_ruamel(self,yaml_file):
        NAME = self.name
        VERSION = self.version
        TAG = self.tag
        ID = NAME+'/'+VERSION+'-'+TAG
        DATA = time.ctime()
        ebfile,build_cmd = self.installpa()
        BUILD_CMD = build_cmd
        eb_sources = self.fetchsources()
        SOURCES = eb_sources       
        EBFILE = ebfile
        depend_cmd,denpendlist = self.listdepend()
        DEPEND_CMD = depend_cmd
        PACKLIST = denpendlist
        # PRESCRIPT = ["home_dir"+"/modules/all","module purge","module load"+" "+self.fullname]
        PRESCRIPT = [str(self._conf.get("home_dir"))+"/modules/all","module purge","module load"+" "+self.fullname]
        py_object = {'$id': ID,
                    '$schema':  'SpModule#SpModuleLocal',
                    'annotation':{'contributors':'liuxj','date':DATA,'email':'lxj@ipp.ac.cn'},
                    'description':'this is a template file. you can refer this template file to produce your own fy_module file of different packages.  If you have any question ,please connet to liuxj(lxj@ipp.ac.cn)',
                    'homepage':'http://funyun.com/demo.html',
                    'information':{
                        'name':NAME,
                        'version':VERSION

                    },
                    'install':{
                        '$class':'EasyBuild',
                        'process':{
                            'fetch':{
                                'sources':SOURCES    
                                },                           
                            'build':{
                                'build_cmd':BUILD_CMD,     
                                'ebfile':EBFILE}
                                },
                            'depend':{
                                'depend_cmd':DEPEND_CMD,
                                'packageslist':PACKLIST},
                            'toolchain':{
                                'tag':TAG},
                                },
                    'license':'GPL',
                    'postscript':'module purge',
                    'prescript': PRESCRIPT,
                    }
        with open(yaml_file, 'w', encoding='utf-8') as file:
            yaml.dump(py_object, file, Dumper=yaml.RoundTripDumper)
            file.close()
        # file = open(yaml_file, 'w', encoding='utf-8')
        # # yaml=YAML(typ='unsafe', pure=True)
        # yaml.dump(py_object, file, Dumper=yaml.RoundTripDumper)
        # file.close()


    def deploy(self,MoResp_dir=None, **kwargs):
        path=self.path
        self.load_configure(path)
        if MoResp_dir == None:
            MoResp_dir = self._conf.get("MoResp_dir")       
        flag,templefile = self.search_tmple_file(MoResp_dir)
        logger.debug(f'the flag and the path  value  is {flag} and {templefile}')
        if flag == 1:
            with open(templefile) as f :
                doc= yaml.load(f,Loader=yaml.FullLoader)
                doc['annotation']['date'] = time.ctime()
                doc['information']['name'] = self.name
                doc['information']['version'] = self.version
                doc['install'][1]['process']['toolchain']['tag'] = self.tag
                depend_cmd,denpendlist = self.listdepend()
                doc['install'][1]['process']['depend']['depend_cmd'] = depend_cmd
                doc['install'][1]['process']['depend']['packageslist'] = denpendlist
                eb_sources = self.fetchsources()
                doc['install'][1]['process']['fetch']['sources'] = eb_sources
                ebfile,build_cmd = self.installpa()
                doc['install'][1]['process']['build']['budild_cmd'] = build_cmd
                doc['install'][1]['process']['build']['ebfile'] = ebfile
                doc['license'] = "GPL"
                prescript = [self._conf.get("home_dir")+"/modules/all","module purge","module load"+" "+self.fullname]
                doc['prescript'] = prescript
            with open(templefile,'w') as f :
                # yaml=YAML(typ='unsafe', pure=True)
                yaml.dump(doc,f,Dumper=yaml.RoundTripDumper)
            desfile = templefile
        else :
            yaml_path = MoResp_dir +"/"+self.name
            if Path(yaml_path).exists() == False :
                Path(yaml_path).mkdir()
            yaml_name = self.modulefullname+".yaml"
            temple_path = os.path.join(yaml_path,yaml_name)
            logger.debug(f'temple-yaml_path and the taml_name is {temple_path} and {yaml_name}')
            self.generate_yaml_doc_ruamel(temple_path)
            desfile = temple_path
        return desfile





