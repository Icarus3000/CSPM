"""External production-path regression only; no native experiment or collector."""
import argparse
import faulthandler
faulthandler.enable()
import ctypes
import json
import os
from pathlib import Path
import platform
import runpy
import shutil
import sys
import tempfile
import time

p=argparse.ArgumentParser()
p.add_argument('--repo',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--development',action='store_true')
p.add_argument('--engine',choices=('native','legacy','reduced'),default='native')
p.add_argument('--missing-bridge',action='store_true')
p.add_argument('--layout-off',action='store_true')
p.add_argument('--font-off',action='store_true')
p.add_argument('--low-performance',action='store_true')
p.add_argument('--default-layout',action='store_true')
p.add_argument('--repair-mode',choices=('both','layout','activation'),default='both')
args=p.parse_args()
repo=args.repo.resolve(); output=args.output.resolve()
assert not output.exists(),'Disposable desktop profile must be new'
output.mkdir(parents=True)
for name in ('data','master','local','roaming','logs','exports','cache','temp'):
    (output/name).mkdir()
for name in ('CSPM.xlsm','Dockets.xlsm'):
    for directory in ('data','master'):
        shutil.copy2(repo/'src/templates'/name,output/directory/name)
for source in (repo/'assets',repo/'src/templates'):
    if source.exists(): shutil.copytree(source,output/source.relative_to(repo))
settings={'appStyle':'Professional','localDataDir':str(output/'data'),'masterDataDir':str(output/'master'),
          'keepTrayAlive':False,'runAtStartup':False,'autoBackupMinutes':0,
          'mainWindowLayout':{'maximized':False,'hasExactRect':True,'x':120,'y':80,'width':960,'height':650,
                             'workAreaX':0,'workAreaY':0,'workAreaWidth':1920,'workAreaHeight':1032}}
settings['masterDataDir']=''
if args.default_layout: settings.pop('mainWindowLayout')
(output/'user_settings.json').write_text(json.dumps(settings))
sys.pycache_prefix=str(output/'cache')
tempfile.tempdir=str(output/'temp')
os.environ.update(APPDATA=str(output/'roaming'),LOCALAPPDATA=str(output/'local'),
                  TEMP=str(output/'temp'),TMP=str(output/'temp'),
                  CSPM_RUNTIME_DIR=str(output),CSPM_DATA_DIR=str(output),CSPM_EXECUTABLE_ROOT=str(output),
                  CSPM_LOG_DIR=str(output/'logs'),CSPM_EXPORT_DIR=str(output/'exports'),
                  PYTHONPYCACHEPREFIX=str(output/'cache'),CSPM_LOW_PERF='1' if args.low_performance else '0',
                  CSPM_DEV_EXPERIMENTS='1',CSPM_DEV_LAYOUT_REPAIRS='1',CSPM_DEV_ACTIVATION_REPAIR='1',
                  CSPM_EXPERIMENTAL_TRANSITION='native-composition',CSPM_EXPERIMENTAL_LAYOUT_REPAIR='1',
                  CSPM_EXPERIMENTAL_ACTIVATION_REPAIR='1')
for key in ('QT_QPA_PLATFORM','QSG_RHI_BACKEND','CSPM_SOFTWARE_RENDER'):
    os.environ.pop(key,None)
for key in tuple(os.environ):
    if key.startswith('CSPM_DEV_') or key.startswith('CSPM_EXPERIMENTAL_'):
        os.environ.pop(key, None)
sys.path.insert(0,str(repo/'src/python'))
platform.__path__=[str(repo/'src/python/platform')]
from backend.motion_settings import write_mode
if args.engine != 'native': write_mode(args.engine)
import backend.native_motion as native_module
if args.missing_bridge: native_module.bridge_path=lambda:output/'missing-bridge.dll'
if args.layout_off:
    from PySide6.QtCore import Property
    class NoLayoutMotion(native_module.NativeMotion):
        @Property(bool,constant=True)
        def layoutRepair(self): return False
    native_module.NativeMotion=NoLayoutMotion
report={'repo':str(repo),'development':args.development,'low_performance':args.low_performance,
        'repair_mode':args.repair_mode,
        'default_preference_absent':args.engine=='native','opt_in_environment_cleared':True,'checks':[],'failures':[],'write_rejections':[],'snapshots':[],
        'engine':args.engine,'missing_bridge':args.missing_bridge,'motion_operations':[],'scope':'Integrated ordinary runtime; synthetic data; real Qt/Windows/WebEngine; no pixel collector or diagnostic native fixture'}

import logging
class MotionRecorder(logging.Handler):
    def emit(self,record):
        report['motion_operations'].append(record.getMessage())
logging.getLogger('motion').addHandler(MotionRecorder())
logging.getLogger('motion').setLevel(logging.INFO)

def audit(event,values):
    if event!='open' or not isinstance(values[0],(str,bytes,os.PathLike)): return
    flags=values[2]
    if not isinstance(flags,int) or not flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND): return
    target=Path(os.fsdecode(values[0]))
    if str(target).upper() in ('NUL','\\\\.\\NUL'): return
    if not target.resolve().is_relative_to(output):
        report['write_rejections'].append(str(target))
        raise PermissionError('Regression writes must remain in disposable profile')
sys.addaudithook(audit)
import winreg
def refuse_registry(*values,**options):
    raise PermissionError('Registry mutation is disabled for disposable regression')
for name in ('SetValueEx','SetValue','DeleteValue','DeleteKey','CreateKey','CreateKeyEx'):
    setattr(winreg,name,refuse_registry)
from PySide6.QtCore import QTimer,Qt,QUrl,QPointF
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlEngine
from PySide6.QtQuick import QQuickItem,QQuickWindow
from PySide6.QtNetwork import QLocalServer
from PySide6.QtTest import QTest
from services.paths import AppPaths
from backend.app_controller import AppController
controller_init=AppController.__init__
def safe_controller(self,paths=None,*values,**options):
    profile=Path(os.environ['CSPM_RUNTIME_DIR'])
    paths=paths or AppPaths(root=profile)
    paths.root=profile
    from repositories.excel_repo import ExcelRepo
    repo_data=ExcelRepo(paths)
    repo_data.ensure_schema()
    report['synthetic_client_ids']=[]; report['synthetic_matter_ids']=[]
    for index in range(1,4):
        client=repo_data.save_client_profile({'clientName':f'AB Synthetic Client {index}','status':'Active'})
        assert client['ok']
        report['synthetic_client_ids'].append(client['clientId'])
        matter=repo_data.save_matter_profile({'clientId':client['clientId'],'clientName':f'AB Synthetic Client {index}',
            'matterName':f'AB Synthetic Matter {index}','dateOpened':'2026-10-09'})
        assert matter['ok']
        report['synthetic_matter_ids'].append(matter['matterId'])
    report['synthetic_records']='Three clients and three matters in disposable workbook only'
    controller_init(self,paths,*values,**options)
AppController.__init__=safe_controller
import main as entry
if args.font_off:
    shutil.copytree(repo/'src/qml',output/'src/qml')
    shutil.copytree(repo/'src/assets',output/'src/assets')
    font=output/'src/qml/standards/HiddenFontMetrics.js'
    font.write_text(font.read_text().replace('function pixelSize(owner, value, enabled) {','function pixelSize(owner, value, enabled) {\n    return value'))
    entry.PROJECT_ROOT=output
    report['font_hold_disabled_in_disposable_mirror']=True
entry._SINGLE_INSTANCE_MUTEX_NAME += '.ABRegression.'+str(os.getpid())
class RegressionServer(QLocalServer):
    @staticmethod
    def removeServer(name): return QLocalServer.removeServer(name+'.ABRegression.'+str(os.getpid()))
    def listen(self,name): return super().listen(name+'.ABRegression.'+str(os.getpid()))
entry.QLocalServer=RegressionServer
entry.APP_TITLE += ' [A/B REGRESSION â€” DISPOSABLE]'
def launch_context():
    screen=QGuiApplication.primaryScreen(); rect=screen.geometry()
    return {'screenIndex':list(QGuiApplication.screens()).index(screen),'cursorX':rect.center().x(),'cursorY':rect.center().y()}
entry._capture_startup_launch_context=launch_context

def capability_reduced(engine):
    return bool(engine.rootContext().contextProperty('nativeMotion').reducedMotion)

class RegressionApp(QApplication):
    def __init__(self,values):
        super().__init__(values)
        self.aboutToQuit.connect(self.persist)
        self.started=time.monotonic(); self.window=None; self.stage='startup'; self.deadline=self.started+100
        self.timer=QTimer(self); self.timer.setInterval(120); self.timer.timeout.connect(self.tick); self.timer.start()
        self.route_index=0; self.direction='maximize'; self.original_rect=None
        self.routes=[('time-entry',1,'B01'),('client-directory',0,'A01'),
            ('new-client',0,'A02'),('client-profile',0,'A03'),('matter-directory',0,'A09'),
            ('matter-wizard',0,'A10'),('matter-profile',0,'A11'),
            ('productivity',3,'D10'),('invoice-preview',2,'C03'),('time-entry-repeat1',1,'B01'),('time-entry-repeat2',1,'B01')]
        QTimer.singleShot(240000,lambda:self.fail('overall regression timeout'))
    def persist(self):
        report['closed']=self.stage=='closing'
        report['elapsed_seconds']=round(time.monotonic()-self.started,3)
        report['actual_profile']=os.environ['CSPM_RUNTIME_DIR']
        (output/'result.json').write_text(json.dumps(report,indent=2))
    def fail(self,message):
        report['failures'].append(message); self.persist(); self.quit()
    def evaluate(self,source):
        value=self.engine.evaluate(source)
        if value.isError(): raise RuntimeError(value.toString())
        return value
    def geometry(self):
        return [self.window.property(n) for n in ('finalX','finalY','finalW','finalH')]
    def snapshot(self,label):
        report['snapshots'].append({'label':label,'final':self.geometry(),
            'uiMaximized':self.window.property('uiMaximized'),'visible':self.window.isVisible(),
            'active':self.window.property('professionalWindowTransitionActive'),
            'screen':self.window.screen().name(),'dpr':self.window.devicePixelRatio(),
            'hwnd_visible':bool(ctypes.windll.user32.IsWindowVisible(int(self.window.winId()))),
            'hwnd_enabled':bool(ctypes.windll.user32.IsWindowEnabled(int(self.window.winId()))),
            'overlay_windows':[w.objectName() for w in self.topLevelWindows() if w.isVisible() and w is not self.window]})
        if not report['snapshots'][-1]['hwnd_visible'] or not report['snapshots'][-1]['hwnd_enabled']:
            report['failures'].append('live HWND visibility/input recovery failed: '+label)
    def tick(self):
        report['last_stage']=self.stage
        self.persist()
        try: self.advance()
        except Exception as exc: self.fail(str(exc))
    def advance(self):
        now=time.monotonic()
        if now>self.deadline: self.fail('stage timeout: '+self.stage); return
        if self.stage=='startup':
            windows=[w for w in self.topLevelWindows() if w.objectName()=='CSPMMainWindow']
            if not windows or windows[0].property('startupPhase')!='post-settle-ready': return
            self.window=windows[0]; self.engine=QQmlEngine.contextForObject(self.window).engine()
            self.engine.globalObject().setProperty('_regressionWindow',self.engine.newQObject(self.window))
            report['screens']=[{'name':s.name(),'dpr':s.devicePixelRatio(),'dpi':s.logicalDotsPerInch(),
                               'geometry':[s.geometry().x(),s.geometry().y(),s.geometry().width(),s.geometry().height()]} for s in self.screens()]
            enabled=bool(self.window.property('layoutRepairEnabled'))
            report['layout_enabled']=enabled
            report['actual_low_performance']=bool(self.window.property('lowPerformanceMode'))
            if report['actual_low_performance']!=args.low_performance:
                self.fail('low-performance request was not applied'); return
            expected_layout=args.engine=='native' and not args.layout_off and not capability_reduced(self.engine)
            if enabled != expected_layout: self.fail('unexpected development capability'); return
            capability=self.engine.rootContext().contextProperty('layoutDevelopment')
            activation=bool(capability.activationRepair) if capability is not None else False
            report['activation_enabled']=activation
            if activation is not True:
                self.fail('unexpected activation capability'); return
            report['checks'].append('opening')
            self.snapshot('startup'); self.webengine(); return
        if self.stage=='webengine': return
        if self.stage=='navigation':
            if now<self.not_before: return
            if self.route_index==0: self.input_check()
            self.original_rect=self.geometry(); self.direction='maximize'; self.command(); return
        if self.stage=='motion':
            if now<self.not_before or self.window.property('professionalWindowTransitionActive') or self.window.property('nativeMotionPreparing'): return
            expected=self.direction=='maximize'
            if bool(self.window.property('uiMaximized')) != expected:
                self.fail('production '+self.direction+' endpoint state'); return
            self.snapshot(self.routes[self.route_index][0]+' '+self.direction)
            if not expected and self.geometry()!=self.original_rect:
                report['failures'].append('production restore geometry changed: '+self.routes[self.route_index][0])
            report['checks'].append(self.routes[self.route_index][0]+' '+self.direction)
            self.input_check()
            if expected:
                self.direction='restore'; self.command(); return
            self.route_index+=1
            if self.route_index<len(self.routes): self.navigate(); return
            if not report.get('mixed_dpi_attempted'):
                other=[(i,s) for i,s in enumerate(self.screens()) if s.devicePixelRatio()!=self.window.devicePixelRatio()]
                report['mixed_dpi_attempted']=bool(other)
                if other:
                    index,screen=other[0]
                    rect=screen.availableGeometry()
                    self.evaluate(f'''_regressionWindow.screen=Qt.application.screens[{index}];
                        _regressionWindow.adoptTargetScreen(Qt.application.screens[{index}],true);
                        _regressionWindow.finalX={rect.x()+80}; _regressionWindow.finalY={rect.y()+60};
                        _regressionWindow.applyHostEnvelopeForTarget(); _regressionWindow.updateCanvasGeometry();''')
                    self.routes.append(('mixed-dpi',1,'B01'))
                    self.navigate(); return
            if self.routes[-1][0]=='mixed-dpi':
                report['mixed_dpi_actual_dpr']=self.window.devicePixelRatio()
            self.stage='minimize'; self.deadline=now+12; self.not_before=now+2
            self.minimize_rect=self.geometry()
            self.evaluate('_regressionWindow.requestMinimizeAnimation()'); return
        if self.stage=='minimize':
            if now<self.not_before: return
            if self.window.visibility()!=QQuickWindow.Minimized:
                return
            report['checks'].append('minimize')
            ctypes.windll.user32.ShowWindow(int(self.window.winId()), 9)
            self.window.requestActivate()
            self.stage='taskbar-return'; self.deadline=now+12; self.not_before=now+2; return
        if self.stage=='taskbar-return':
            if now<self.not_before or self.window.property('isRestoringFromMinimize'): return
            if not self.window.isVisible() or self.geometry()!=self.minimize_rect:
                self.fail('taskbar return lost visibility/normal rectangle'); return
            report['checks'].append('taskbar return')
            self.evaluate('_regressionWindow.mainContentRef.option3OpenWorkspaceForTile(1,"B01",{})')
            QTest.qWait(400)
            self.input_check()
            self.stage='closing'; self.deadline=now+20
            self.evaluate('_regressionWindow.requestCloseAnimation()'); return
        if self.stage=='closing' and not self.window.isVisible():
            report['checks'].append('closing'); self.persist(); self.quit()
    def command(self):
        self.stage='motion'; self.deadline=time.monotonic()+12; self.not_before=time.monotonic()+.5
        self.evaluate('_regressionWindow.toggleWindowMaximize()')
        if self.route_index == 9:
            for _ in range(6): self.evaluate('_regressionWindow.toggleWindowMaximize()')
            report.setdefault('rapid_request_bursts',0)
            report['rapid_request_bursts'] += 1
    def navigate(self):
        label,tile,node=self.routes[self.route_index]
        params={}
        if node=='A03': params={'clientId':report['synthetic_client_ids'][0]}
        if node=='A11': params={'matterId':report['synthetic_matter_ids'][0]}
        self.evaluate(f'_regressionWindow.mainContentRef.option3OpenWorkspaceForTile({tile}, "{node}", {json.dumps(params)})')
        self.stage='navigation'; self.deadline=time.monotonic()+15; self.not_before=time.monotonic()+2
    def input_check(self):
        candidates=[i for i in self.window.findChildren(QQuickItem) if i.isVisible() and i.isEnabled()
            and i.width()>0 and i.height()>0 and i.opacity()>0
            and i.metaObject().indexOfProperty('text')>=0
            and any(n in i.metaObject().className() for n in ('TextArea','TextField','TextEdit'))
            and not i.property('readOnly') and not i.property('inputMask')]
        candidates.sort(key=lambda i:0 if 'TextArea' in i.metaObject().className() else 1)
        candidates=[i for i in candidates if i.window() is self.window and 0 <= i.mapToScene(QPointF(i.width()/2,i.height()/2)).x() < self.window.width() and 0 <= i.mapToScene(QPointF(i.width()/2,i.height()/2)).y() < self.window.height()]
        if not candidates:
            report.setdefault('input_unavailable_routes',[]).append(self.routes[self.route_index][0]); return
        item=candidates[0]; before=str(item.property('text') or '')
        self.window.requestActivate(); QTest.qWait(100)
        QTest.mouseClick(self.window,Qt.LeftButton,Qt.NoModifier,
            item.mapToScene(QPointF(item.width()/2,item.height()/2)).toPoint())
        QTest.qWait(100)
        if item.hasActiveFocus(): report['checks'].append('actual mouse focus')
        else: report['failures'].append('mouse click did not focus editable input')
        item.forceActiveFocus(); QTest.qWait(100)
        QTest.keyClick(self.window,Qt.Key_Z); QTest.qWait(50)
        after=str(item.property('text') or '')
        report.setdefault('input_observations',[]).append({'class':item.metaObject().className(),
            'activeFocus':item.hasActiveFocus(),'before_length':len(before),'after_length':len(after)})
        if before==after or not item.hasActiveFocus(): report['failures'].append('focus/key input was not accepted')
        else: report['checks'].append('focus and actual key input')
        item.setProperty('text',before)
    def webengine(self):
        from PySide6.QtWebEngineWidgets import QWebEngineView
        from PySide6.QtWebEngineCore import QWebEnginePage,QWebEngineProfile
        self.web=QWebEngineView(); self.web.setWindowTitle('A/B WebEngine regression â€” disposable')
        profile=QWebEngineProfile('AB-regression-'+str(os.getpid()),self.web)
        profile.setCachePath(str(output/'cache/webengine')); profile.setPersistentStoragePath(str(output/'cache/web-storage'))
        self.web.setPage(QWebEnginePage(profile,self.web))
        self.stage='webengine'; self.deadline=time.monotonic()+30
        def loaded(ok):
            if not ok: self.fail('WebEngine HTML load failed'); return
            self.web.page().runJavaScript('document.body.textContent',verified)
        def verified(value):
            if 'SYNTHETIC-WEBENGINE-PASS' not in str(value): self.fail('WebEngine JS/render marker failed'); return
            report['checks'].append('real WebEngine HTML/JavaScript')
            self.web.close(); self.window.requestActivate(); self.navigate()
        self.web.loadFinished.connect(loaded)
        self.web.resize(480,240); self.web.show()
        self.web.setHtml('<html><body style="background:#223344;color:white">SYNTHETIC-WEBENGINE-PASS</body></html>',QUrl('about:blank'))

entry.QApplication=RegressionApp
try:
    if args.development:
        sys.argv=[str(repo/'scripts/launch_layout_repair_dev.py'),'--profile-parent',str(output)]
        if args.repair_mode in ('both','layout'): sys.argv.append('--layout-repair')
        if args.repair_mode in ('both','activation'): sys.argv.append('--activation-repair')
        runpy.run_path(sys.argv[0],run_name='__main__')
    else:
        entry.main()
except SystemExit as exc:
    if not (output/'result.json').exists():
        report['failures'].append('entry exited before lifecycle results: '+str(exc))
        (output/'result.json').write_text(json.dumps(report,indent=2))
    raise
except BaseException as exc:
    report['failures'].append('uncaught runner error: '+type(exc).__name__+': '+str(exc))
    (output/'result.json').write_text(json.dumps(report,indent=2))
    raise
