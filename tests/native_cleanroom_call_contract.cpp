// Native wait/error/retention contract; creates no HWND, GPU, Qt or WebEngine.
#include "../src/native/cleanroom_composition/cleanroom_composition.cpp"
#include <cassert>
int main() {
    assert(cspm_comp_abi_version()==1);
    assert(sizeof(NativeWindowState)==152 && sizeof(NativeCallRow)==896 && sizeof(NativeCallTrace)==230312);
    assert(nativeWaitState(WAIT_OBJECT_0)==1);
    assert(nativeWaitState(WAIT_TIMEOUT)==2);
    assert(nativeWaitState(WAIT_FAILED)==3);
    assert(nativeWaitState(WAIT_ABANDONED_0)==4);
    assert(nativeWaitState(WAIT_IO_COMPLETION)==5);
    assert(!nativeCallFailed(NativeFrameSlotWait,WAIT_OBJECT_0));
    assert(nativeCallFailed(NativeFrameSlotWait,WAIT_TIMEOUT));
    assert(nativeCallFailed(NativeFrameSlotWait,WAIT_FAILED));
    assert(nativeCallFailed(NativeFrameSlotWait,WAIT_ABANDONED_0));
    assert(!nativeCallFailed(NativePresent,uint32_t(S_OK)));
    assert(nativeCallFailed(NativePresent,uint32_t(E_FAIL)));
    assert(nativeCallFailed(NativeAcquireSharedMutex,uint32_t(WAIT_TIMEOUT)));
    assert(!nativeCallFailed(NativeHideHost,0));
    Host ordinary;
    assert(!ordinary.nativeCallTraceEnabled.load() && !ordinary.nativeCallTrace);
    SetLastError(99);
    unsigned invoked=0;
    const DWORD ordinaryResult=nativeInvoke(ordinary,NativeFrameSlotWait,100,0,0,true,[&] {
        ++invoked; SetLastError(77); return DWORD(WAIT_TIMEOUT); });
    assert(ordinaryResult==WAIT_TIMEOUT && invoked==1 && GetLastError()==77);
    assert(!ordinary.nativeCallTrace && !ordinary.nativeQpcFrequency);
    auto output=std::make_unique<NativeCallTrace>();
    assert(cspm_comp_enable_native_call_trace(nullptr)==0);
    assert(cspm_comp_set_native_trace_live(nullptr,1)==0);
    assert(cspm_comp_set_native_trace_live(&ordinary,0)==0);
    assert(cspm_comp_set_native_trace_live(&ordinary,1)==0);
    assert(cspm_comp_native_call_trace(nullptr,output.get(),sizeof(*output))==0);
    assert(cspm_comp_native_call_trace(&ordinary,nullptr,sizeof(*output))==0);
    assert(cspm_comp_native_call_trace(&ordinary,output.get(),sizeof(*output)-1)==0);
    assert(cspm_comp_native_call_trace(&ordinary,output.get(),sizeof(*output))==0);
    assert(cspm_comp_destroy_with_native_call_trace(nullptr,output.get(),sizeof(*output))==0);
    assert(cspm_comp_destroy_with_native_call_trace(&ordinary,nullptr,sizeof(*output))==0);
    assert(cspm_comp_destroy_with_native_call_trace(&ordinary,output.get(),sizeof(*output)-1)==0);
    assert(cspm_comp_destroy_with_native_call_trace(&ordinary,output.get(),sizeof(*output))==0);
    assert(!ordinary.flags.load() && !ordinary.nativeCallTrace); // Rejections leave host untouched.
    Host traced;
    traced.nativeCallTrace=std::make_unique<NativeCallTrace>(); traced.nativeCallTrace->enabled=1;
    LARGE_INTEGER frequency{}; QueryPerformanceFrequency(&frequency);
    traced.nativeQpcFrequency=uint64_t(frequency.QuadPart);
    traced.nativeCallTraceEnabled.store(true); traced.workerThreadId=GetCurrentThreadId();
    traced.flags=1|2|8; traced.source.frameRevision=101; traced.destination.frameRevision=202;
    traced.source.resourceIdentity=303; traced.destination.resourceIdentity=404;
    traced.submittedCount=7; traced.displayedCount=6;
    const DWORD rejected=nativeInvoke(traced,NativeFrameSlotWait,100,0,0,true,[] {
        SetLastError(ERROR_INVALID_HANDLE); return DWORD(WAIT_FAILED); });
    // Null-window diagnostic queries overwrite OS last-error; both the saved
    // row and caller's immediate error remain the primary failure nonetheless.
    assert(rejected==WAIT_FAILED && GetLastError()==ERROR_INVALID_HANDLE);
    assert(cspm_comp_native_call_trace(&traced,output.get(),sizeof(*output))==1);
    const auto& first=output->rows[0];
    assert(output->enabled && output->count==1 && output->totalRows==1 && !output->droppedRows);
    assert(output->hasFirstFailure && output->firstFailure.result==WAIT_FAILED);
    assert(first.result==WAIT_FAILED && first.win32Error==ERROR_INVALID_HANDLE && first.lastErrorApplicable==1);
    assert(first.call==NativeFrameSlotWait && first.phase==3 && first.timeoutMs==100);
    assert(first.waitStateBefore==0 && first.waitStateAfter==3 && !first.alertable);
    assert(first.startQpc<=first.returnQpc && first.qpcFrequency==traced.nativeQpcFrequency);
    assert(first.beginSeconds<=first.returnSeconds && first.currentThread==GetCurrentThreadId());
    assert(first.expectedHostGeneration==traced.generation && first.hostGeneration==traced.generation);
    assert(first.sourceGeneration==101 && first.targetGeneration==202);
    assert(first.expectedSourceGeneration==101 && first.expectedTargetGeneration==202);
    assert(first.sourceResourceIdentity==303 && first.targetResourceIdentity==404);
    assert(first.expectedPresentId==8 && first.submittedBefore==7 && first.submittedAfter==7);
    assert(first.displayedBefore==6 && first.displayedAfter==6 && first.bufferIndex==UINT32_MAX);
    assert(!first.beforeMotion && !first.keyedMutexState && !first.fenceState);
    assert(first.nativeBefore.queryErrors==1 && first.nativeAfter.queryErrors==1);
    traced.fail("first terminal failure");
    nativeInvoke(traced,NativeSourceBandPosition,0,0,0,true,[] { SetLastError(ERROR_ACCESS_DENIED); return FALSE; });
    assert(GetLastError()==ERROR_ACCESS_DENIED);
    assert(cspm_comp_native_call_trace(&traced,output.get(),sizeof(*output))==1);
    assert(output->firstFailure.call==NativeFrameSlotWait && output->firstFailure.win32Error==ERROR_INVALID_HANDLE);
    nativeInvoke(traced,NativeCompositionCommit,0,0,0,false,[] { return S_OK; });
    nativeInvoke(traced,NativeCommitCompletion,UINT32_MAX,0,0,false,[] { return E_FAIL; });
    nativeInvoke(traced,NativeAcquireSharedMutex,40,505,1,false,[] { return HRESULT(WAIT_TIMEOUT); });
    nativeInvoke(traced,NativeReleaseSharedMutex,0,505,1,false,[] { return S_OK; });
    assert(cspm_comp_native_call_trace(&traced,output.get(),sizeof(*output))==1);
    assert(output->rows[2].commitBefore==0 && output->rows[2].commitAfter==1);
    assert(output->rows[3].timeoutMs==UINT32_MAX && output->rows[3].commitBefore==1);
    assert(output->rows[4].phase==4 && output->rows[4].expectedTargetGeneration==505);
    assert(output->rows[4].keyedMutexKey==1 && output->rows[4].keyedMutexState==2);
    assert(output->rows[5].keyedMutexState==3);
    output->version=2; assert(cspm_comp_native_call_trace(&traced,output.get(),sizeof(*output))==0);
    output->version=1; output->byteSize=1; assert(cspm_comp_native_call_trace(&traced,output.get(),sizeof(*output))==0);
    output->byteSize=sizeof(*output); output->rowByteSize=1;
    assert(cspm_comp_native_call_trace(&traced,output.get(),sizeof(*output))==0);
    output->rowByteSize=sizeof(NativeCallRow);
    Host bounded;
    bounded.nativeCallTrace=std::make_unique<NativeCallTrace>(); bounded.nativeCallTrace->enabled=1;
    bounded.nativeCallTraceEnabled.store(true);
    NativeCallRow row; row.call=NativeFrameStatistics; row.result=uint32_t(DXGI_ERROR_FRAME_STATISTICS_DISJOINT);
    nativeStoreCall(bounded,row);
    row.call=NativeLastPresentCount; nativeStoreCall(bounded,row);
    assert(!bounded.nativeCallTrace->hasFirstFailure);
    row.call=NativeValidateSourceBand; row.result=0; nativeStoreCall(bounded,row);
    row.call=NativePresent; row.result=S_OK;
    for(unsigned i=0;i<300;++i) nativeStoreCall(bounded,row);
    assert(cspm_comp_native_call_trace(&bounded,output.get(),sizeof(*output))==1);
    assert(output->totalRows==303 && output->count==256 && output->droppedRows==47);
    assert(output->rows[0].sequence==48 && output->rows[255].sequence==303);
    assert(output->hasFirstFailure && output->firstFailure.sequence==3);
    assert(output->firstFailure.call==NativeValidateSourceBand);
    for(unsigned i=1;i<256;++i) assert(output->rows[i].sequence==output->rows[i-1].sequence+1);
    return 0;
}
