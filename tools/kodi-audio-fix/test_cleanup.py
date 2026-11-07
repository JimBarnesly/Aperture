#!/usr/bin/env python3
"""Focused host harness of actual distro method bodies, not full Kodi/audio integration."""
from pathlib import Path
import subprocess, os
root=Path(os.environ['TEST_OUTPUT'])
root.mkdir(parents=True, exist_ok=True)
src=Path(os.environ['KODI_SOURCE'])/'xbmc'
pre=r'''
#include <cassert>
#include <memory>
#include <map>
#include <iostream>
int created=0, destroyed=0, retroClosed=0, wrapperClosed=0, enabled=0;
bool failOpen=true;
enum GAME_STREAM_TYPE { GAME_STREAM_AUDIO, GAME_STREAM_VIDEO, GAME_STREAM_SW_FRAMEBUFFER, INVALID };
struct game_stream_properties { GAME_STREAM_TYPE type; };
constexpr int LOGERROR=1;
struct CLog { template<class... T> static void Log(T...) {} };
namespace KODI {
namespace RETRO {
enum class StreamType { AUDIO, VIDEO, SW_BUFFER, HW_BUFFER };
struct IRetroPlayerStream { virtual ~IRetroPlayerStream(){ ++destroyed; } virtual void CloseStream(){ ++retroClosed; } };
using StreamPtr=std::unique_ptr<IRetroPlayerStream>;
struct CRPRenderManager{}; struct CRPProcessInfo{};
struct CRetroPlayerAudio : IRetroPlayerStream { CRetroPlayerAudio(CRPProcessInfo&){++created;} void Enable(bool){++enabled;} };
struct CRetroPlayerVideo : IRetroPlayerStream { CRetroPlayerVideo(CRPRenderManager&, CRPProcessInfo&){++created;} };
struct IStreamManager { virtual ~IStreamManager()=default; virtual StreamPtr CreateStream(StreamType)=0; virtual void CloseStream(StreamPtr)=0; };
struct CRPStreamManager : IStreamManager {
 CRPStreamManager(CRPRenderManager&,CRPProcessInfo&);
 void EnableAudio(bool); StreamPtr CreateStream(StreamType) override; void CloseStream(StreamPtr) override;
 CRPRenderManager& m_renderManager; CRPProcessInfo& m_processInfo; CRetroPlayerAudio* m_audioStream=nullptr;
};
}
namespace GAME {
struct CGameClient { double GetSampleRate(){return 48000;} };
struct IGameClientStream { virtual ~IGameClientStream()=default; virtual bool OpenStream(RETRO::IRetroPlayerStream*,const game_stream_properties&){return !failOpen;} virtual void CloseStream(){++wrapperClosed;} };
struct CGameClientStreamAudio : IGameClientStream { CGameClientStreamAudio(double){} };
struct CGameClientStreamVideo : IGameClientStream {};
struct CGameClientStreamSwFramebuffer : IGameClientStream {};
struct CGameClientTranslator { static bool TranslateStreamType(GAME_STREAM_TYPE t, RETRO::StreamType& r){if(t==INVALID)return false; r=t==GAME_STREAM_AUDIO?RETRO::StreamType::AUDIO:RETRO::StreamType::VIDEO; return true;} };
struct CGameClientStreams {
 CGameClientStreams(CGameClient&); void Initialize(RETRO::IStreamManager&); void Deinitialize();
 IGameClientStream* OpenStream(const game_stream_properties&); void CloseStream(IGameClientStream*);
 std::unique_ptr<IGameClientStream> CreateStream(GAME_STREAM_TYPE) const;
 CGameClient& m_gameClient; RETRO::IStreamManager* m_streamManager=nullptr;
 std::map<IGameClientStream*,RETRO::StreamPtr> m_streams;
};
}
}
'''
post=r'''
int main(){
 KODI::GAME::CGameClient client; KODI::GAME::CGameClientStreams streams(client);
 KODI::RETRO::CRPRenderManager render; KODI::RETRO::CRPProcessInfo info;
 KODI::RETRO::CRPStreamManager manager(render,info);
 assert(streams.OpenStream({GAME_STREAM_AUDIO})==nullptr); assert(created==0);
 streams.Initialize(manager);
 assert(streams.OpenStream({INVALID})==nullptr); assert(created==0);
 for(int i=0;i<100;i++) {
  assert(streams.OpenStream({GAME_STREAM_AUDIO})==nullptr);
  assert(manager.m_audioStream==nullptr); assert(streams.m_streams.empty());
  assert(created==i+1 && destroyed==i+1 && retroClosed==i+1 && wrapperClosed==i+1);
  manager.EnableAudio(false); manager.EnableAudio(true); assert(enabled==0);
 }
 failOpen=false; auto* good=streams.OpenStream({GAME_STREAM_AUDIO});
 assert(good && manager.m_audioStream && streams.m_streams.size()==1);
 manager.EnableAudio(false); manager.EnableAudio(true); assert(enabled==2);
 streams.CloseStream(good); assert(manager.m_audioStream==nullptr && streams.m_streams.empty());
 assert(created==101 && destroyed==101 && retroClosed==101 && wrapperClosed==101);
 streams.Deinitialize(); assert(streams.OpenStream({GAME_STREAM_AUDIO})==nullptr);
 std::cout<<"PASS: early failure, 100 failed opens, post-failure audio toggles, successful retry, close\n";
}
'''
def body(path):
 return '\n'.join(l for l in path.read_text().splitlines() if not l.startswith('#include'))+'\n'
client_body=body(src/'games/addons/streams/GameClientStreams.cpp')
manager_body=body(src/'cores/RetroPlayer/streams/RPStreamManager.cpp')
for label,cb in [('patched',client_body),('baseline',client_body.replace('    gameStream->CloseStream();\n    m_streamManager->CloseStream(std::move(retroStream));\n',''))]:
 cpp=root/f'harness-{label}.cpp'; exe=root/f'harness-{label}'
 cpp.write_text(pre+cb+manager_body+post)
 subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-g','-fsanitize=address,undefined',str(cpp),'-o',str(exe)],check=True)
 result=subprocess.run([str(exe)],capture_output=True,text=True,env={**os.environ,"ASAN_OPTIONS":"detect_leaks=0"})
 (root/f'test-{label}.log').write_text(result.stdout+result.stderr)
 print(label,'returncode',result.returncode,result.stdout,result.stderr[:400])
 assert (result.returncode==0)==(label=='patched')
