package com.aven.calls;

import static org.junit.Assert.*;
import android.app.*;
import android.content.*;
import android.net.Uri;
import android.os.SystemClock;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import androidx.test.uiautomator.*;
import java.io.*;
import java.net.*;
import java.nio.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;
import org.junit.*;
import org.junit.runner.RunWith;

/** Local HTTP/Android integration tests; no working CRM records are changed. */
@RunWith(AndroidJUnit4.class)
public class CrmHistoryTest {
  private AvenApplication app;
  private LeadActivity activity;
  private UiDevice device;
  private String pkg,origin;
  private ServerSocket listener;
  private Thread server;
  private byte[] wav;
  private JSONObject recording;
  private final Map<String,Reply> routes=new ConcurrentHashMap<>();
  private final List<String> requests=new CopyOnWriteArrayList<>();
  private record Reply(int status,byte[] body,String mime,Runnable before) {}

  @Before public void setup() throws Exception {
    var instrumentation=InstrumentationRegistry.getInstrumentation();
    app=(AvenApplication)instrumentation.getTargetContext().getApplicationContext();
    assertTrue(app.getPackageName().endsWith(".debug"));
    app.api.cancelActive();SyncScheduler.cancel(app);SyncEngine.LOCK.lock();
    try{app.resetLocalData();app.session.clear();}finally{SyncEngine.LOCK.unlock();}
    app.store.meta("enabled","false");
    listener=new ServerSocket(0);origin="http://127.0.0.1:"+listener.getLocalPort();pkg=app.getPackageName();
    device=UiDevice.getInstance(instrumentation);
    app.session.putAll(new JSONObject().put("server",origin).put("user_id","caller").put("org_id","company")
        .put("access","test-access").put("refresh","test-refresh").put("name","Test caller").put("role","telecaller"));
    wav=wav();
    recording=new JSONObject().put("id","recording-a").put("lead_id","lead-a").put("org_id","company")
        .put("name","Saved CRM call.wav").put("mime","audio/wav").put("size",wav.length)
        .put("digest",hex(MessageDigest.getInstance("SHA-256").digest(wav))).put("created_at","2026-10-24T10:00:00Z");
    json("/api/auth/me",200,new JSONObject());
    json("/api/leads/lead-a",200,lead());
    json("/api/leads/lead-a/history?page=1&size=20",200,history(false));
    json("/api/leads/lead-a/history?page=2&size=20",200,history(true));
    routes.put("/api/files/recording-a",new Reply(200,wav,"audio/wav",null));
    server=new Thread(()->{
      while(!listener.isClosed())try(Socket socket=listener.accept()){
        socket.setSoTimeout(10000);
        BufferedReader in=new BufferedReader(new InputStreamReader(socket.getInputStream(),StandardCharsets.UTF_8));
        String first=in.readLine();if(first==null)continue;String path=first.split(" ")[1];
        String authorization="",line;int length=0;
        while((line=in.readLine())!=null && !line.isEmpty()){
          if(line.toLowerCase(Locale.ROOT).startsWith("authorization:"))authorization=line.substring(14).trim();
          if(line.toLowerCase(Locale.ROOT).startsWith("content-length:"))length=Integer.parseInt(line.substring(15).trim());
        }
        while(length-->0)in.read();
        requests.add(path+"|"+authorization);
        Reply reply=routes.getOrDefault(path,new Reply(404,"{}".getBytes(StandardCharsets.UTF_8),"application/json",null));
        if(reply.before()!=null)reply.before().run();
        byte[] header=("HTTP/1.1 "+reply.status()+" Result\r\nContent-Type: "+reply.mime()+"\r\nContent-Length: "+reply.body().length+"\r\nConnection: close\r\n\r\n").getBytes(StandardCharsets.UTF_8);
        socket.getOutputStream().write(header);socket.getOutputStream().write(reply.body());
      }catch(Exception ignored){}
    });server.start();
  }
  @After public void cleanup() throws Exception {
    if(activity!=null)InstrumentationRegistry.getInstrumentation().runOnMainSync(activity::finish);
    app.api.cancelActive();listener.close();server.join(12000);app.session.clear();SyncScheduler.cancel(app);
    for(File f:previews())f.delete();
  }
  private File[] previews(){File[] files=app.getCacheDir().listFiles((d,n)->n.startsWith("aven-preview-"));return files==null?new File[0]:files;}
  private String hex(byte[] bytes){StringBuilder s=new StringBuilder();for(byte b:bytes)s.append(String.format(Locale.ROOT,"%02x",b&255));return s.toString();}
  private byte[] wav(){
    int samples=8000*30;ByteBuffer b=ByteBuffer.allocate(44+samples*2).order(ByteOrder.LITTLE_ENDIAN);
    b.put("RIFF".getBytes(StandardCharsets.US_ASCII)).putInt(36+samples*2).put("WAVEfmt ".getBytes(StandardCharsets.US_ASCII))
        .putInt(16).putShort((short)1).putShort((short)1).putInt(8000).putInt(16000).putShort((short)2).putShort((short)16)
        .put("data".getBytes(StandardCharsets.US_ASCII)).putInt(samples*2);return b.array();
  }
  private void json(String path,int status,JSONObject value){routes.put(path,new Reply(status,value.toString().getBytes(StandardCharsets.UTF_8),"application/json",null));}
  private JSONObject lead() throws Exception{return new JSONObject().put("id","lead-a").put("org_id","company").put("name","CRM buyer").put("phone","+919810001234").put("notes","Buyer prefers a corner plot").put("dnd",false);}
  private JSONObject history(boolean older) throws Exception {
    JSONArray calls=new JSONArray();int count=older?1:20;
    for(int i=0;i<count;i++)calls.put(new JSONObject().put("id",(older?"older":"call")+i).put("lead_id","lead-a").put("org_id","company")
        .put("direction","incoming").put("result","answered").put("duration",12).put("user_id","caller")
        .put("started_at","2026-10-24T10:00:00Z").put("recordings",i==0&&!older?new JSONArray().put(recording):new JSONArray()));
    return new JSONObject().put("phone_calls",calls).put("manual_calls",new JSONArray())
        .put("notes",older?new JSONArray():new JSONArray().put(new JSONObject().put("text","Discussed Sector 18 plot").put("author_id","caller").put("created_at","2026-10-24T10:00:00Z")))
        .put("tasks",older?new JSONArray():new JSONArray().put(new JSONObject().put("title","Arrange site visit").put("state","open").put("due_at","2026-10-26T10:00:00Z")))
        .put("files",older?new JSONArray():new JSONArray().put(recording))
        .put("activity",older?new JSONArray():new JSONArray().put(new JSONObject().put("summary","Lead ownership updated").put("actor_id","caller").put("created_at","2026-10-24T10:00:00Z")))
        .put("people",new JSONObject().put("caller","Test caller"))
        .put("pagination",new JSONObject().put("page",older?2:1).put("size",20).put("totals",new JSONObject().put("phone_calls",21).put("manual_calls",0).put("notes",1).put("tasks",1).put("files",1).put("activity",1)));
  }
  private void start(){activity=(LeadActivity)InstrumentationRegistry.getInstrumentation().startActivitySync(new Intent(app,LeadActivity.class).putExtra("lead_id","lead-a").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TASK));}
  private UiObject2 find(String id) throws Exception {
    UiObject2 result=device.wait(Until.findObject(By.res(pkg,id)),1000);
    if(result==null){
      if(Set.of("crm_calls","crm_notes","crm_activity","crm_tasks","crm_files").contains(id))
        new UiScrollable(new UiSelector().className("android.widget.HorizontalScrollView")).setAsHorizontalList().scrollIntoView(new UiSelector().resourceId(pkg+":id/"+id));
      else new UiScrollable(new UiSelector().className("android.widget.ScrollView")).setMaxSearchSwipes(40).scrollIntoView(new UiSelector().resourceId(pkg+":id/"+id));
      result=device.wait(Until.findObject(By.res(pkg,id)),5000);
    }
    assertNotNull(id,result);
    // Partly visible controls need their entire touch target scrolled above navigation insets.
    if(activity!=null){
      int viewId=app.getResources().getIdentifier(id,"id",pkg);
      InstrumentationRegistry.getInstrumentation().runOnMainSync(()->{
        android.view.View target=activity.findViewById(viewId);
        if(target!=null)target.requestRectangleOnScreen(new android.graphics.Rect(0,0,target.getWidth(),target.getHeight()),true);
      });
      device.waitForIdle();result=device.findObject(By.res(pkg,id));
    }
    assertNotNull(id,result);return result;
  }
  private void expect(String value) throws Exception {
    if(!device.wait(Until.hasObject(By.text(value)),1500))new UiScrollable(new UiSelector().className("android.widget.ScrollView")).setMaxSearchSwipes(40).scrollIntoView(new UiSelector().text(value));
    boolean found=device.wait(Until.hasObject(By.text(value)),5000);
    if(!found){device.takeScreenshot(new File(app.getExternalFilesDir(null),"qa-crm-failure.png"));device.dumpWindowHierarchy(new File(app.getExternalFilesDir(null),"qa-crm-failure.xml"));}
    assertTrue(value,found);
  }
  private void loaded() throws Exception {expect("21 synced calls · 1 file");}

  @Test public void serverHistoryIsVisibleWithoutAnyLocalCallsAndTabsPaginate() throws Exception {
    start();loaded();assertEquals(0,app.store.query("SELECT * FROM calls").size());assertFalse(app.enabled());
    find("crm_next").click();expect("Calls · Page 2 of 2");find("crm_previous").click();expect("Calls · Page 1 of 2");
    find("crm_notes").click();expect("Buyer prefers a corner plot");expect("Discussed Sector 18 plot");
    find("crm_activity").click();expect("Lead ownership updated");
    find("crm_tasks").click();expect("Arrange site visit");
    find("crm_files").click();expect("Saved CRM call.wav");find("crm_play");
    InstrumentationRegistry.getInstrumentation().runOnMainSync(()->checkLayout(activity.getWindow().getDecorView()));
    assertFalse(device.hasObject(By.text(java.util.regex.Pattern.compile("(?i).*delete.*"))));
    assertTrue(requests.stream().anyMatch(s->s.equals("/api/leads/lead-a/history?page=2&size=20|Bearer test-access")));
  }
  @Test public void recordingDecodesPausesSeeksAndPrivateCopyIsRemovedOnClose() throws Exception {
    start();loaded();find("crm_play").click();expect("Playing");
    assertTrue(device.wait(Until.hasObject(By.res(pkg,"crm_media_time").textContains("/ 30s")),5000));
    device.takeScreenshot(new File(app.getExternalFilesDir(null),"qa-crm-player.png"));
    find("crm_audio_toggle").click();expect("Paused");
    UiObject2 seek=find("crm_seek");android.graphics.Rect rect=seek.getVisibleBounds();device.click(rect.centerX(),rect.centerY());
    find("crm_audio_toggle").click();expect("Playing");device.pressBack();
    long end=SystemClock.elapsedRealtime()+3000;while(previews().length>0 && SystemClock.elapsedRealtime()<end)SystemClock.sleep(50);
    assertEquals(0,previews().length);
    assertTrue(requests.contains("/api/files/recording-a|Bearer test-access"));
    assertEquals(0,app.store.query("SELECT * FROM calls").size());
  }
  @Test public void backgroundingStopsPlaybackAndRemovesPrivateCopy() throws Exception {
    start();loaded();find("crm_play").click();expect("Playing");device.pressHome();
    long end=SystemClock.elapsedRealtime()+3000;while(previews().length>0 && SystemClock.elapsedRealtime()<end)SystemClock.sleep(50);
    assertEquals(0,previews().length);
  }
  @Test public void changingTabsDuringDownloadDoesNotOpenAPlayerLater() throws Exception {
    var received=new CountDownLatch(1);var release=new CountDownLatch(1);
    routes.put("/api/files/recording-a",new Reply(200,wav,"audio/wav",()->{
      received.countDown();try{release.await(5,TimeUnit.SECONDS);}catch(InterruptedException e){Thread.currentThread().interrupt();}
    }));
    try{
      start();loaded();find("crm_play").click();assertTrue(received.await(5,TimeUnit.SECONDS));
      find("crm_notes").click();release.countDown();expect("Discussed Sector 18 plot");SystemClock.sleep(300);
      assertFalse(device.hasObject(By.res(pkg,"crm_media_status")));assertEquals(0,previews().length);
    }finally{release.countDown();}
  }
  @Test public void unavailableHistoryShowsRetryAndDoesNotPretendThereAreNoCalls() throws Exception {
    json("/api/leads/lead-a/history?page=1&size=20",503,new JSONObject());start();expect("History couldn't be loaded");
    assertFalse(device.hasObject(By.text("No synced calls yet")));
    json("/api/leads/lead-a/history?page=1&size=20",200,history(false));find("crm_retry").click();loaded();
  }
  @Test public void returningToFailedHistoryRetriesWithoutTouchingPendingCalls() throws Exception {
    app.store.capture("keep-history-recovery","+919810001234","Queued",System.currentTimeMillis(),10,"incoming","answered");
    json("/api/leads/lead-a/history?page=1&size=20",503,new JSONObject());start();expect("History couldn't be loaded");
    var instrumentation=InstrumentationRegistry.getInstrumentation();
    instrumentation.runOnMainSync(()->instrumentation.callActivityOnPause(activity));
    json("/api/leads/lead-a/history?page=1&size=20",200,history(false));
    instrumentation.runOnMainSync(()->instrumentation.callActivityOnResume(activity));
    loaded();
    assertFalse("The existing screen must recover",activity.isDestroyed());
    assertNotNull(activity.findViewById(R.id.crm_summary));
    assertEquals(2,requests.stream().filter(s->s.startsWith("/api/leads/lead-a/history?")).count());
    assertEquals("pending",app.store.query("SELECT state FROM calls WHERE id='keep-history-recovery'").get(0).get("state"));
    assertFalse(app.enabled());
  }
  @Test public void upstreamHtml404DoesNotClaimTheLeadWasReassigned() throws Exception {
    routes.put("/api/leads/lead-a",new Reply(404,"<html>Temporary tunnel unavailable</html>".getBytes(StandardCharsets.UTF_8),"text/html",null));
    start();expect("History couldn't be loaded");
    expect("Check your connection and tap Try again. Your calls remain saved in the CRM.");
    assertFalse(device.hasObject(By.text("This lead is no longer available to your account. Return to Leads and refresh your assignments.")));
    json("/api/leads/lead-a",200,lead());find("crm_retry").click();loaded();
  }
  @Test public void suspendedCompanyShowsTheAccountReasonInsteadOfReassignment() throws Exception {
    json("/api/leads/lead-a",403,new JSONObject().put("error",new JSONObject()
        .put("code","organization_suspended").put("message","This organization is suspended")));
    start();expect("History couldn't be loaded");
    expect("Your company account is suspended. Contact your administrator.");
    assertFalse(device.hasObject(By.text("CRM buyer")));
  }
  @Test public void lostLeadAccessHidesPreviouslyLoadedHistory() throws Exception {
    start();loaded();json("/api/leads/lead-a",404,new JSONObject().put("error",new JSONObject().put("code","not_found").put("message","This lead is not available to you")));find("crm_refresh").click();expect("History couldn't be loaded");
    expect("This lead is no longer available to your account. Return to Leads and refresh your assignments.");
    assertFalse(device.hasObject(By.text("CRM buyer")));assertFalse(device.hasObject(By.text("Play recording")));
  }
  @Test public void sessionExpiryClosesScreenWithoutClearingQueuedCalls() throws Exception {
    app.store.capture("safe","+919810001234","Queued",System.currentTimeMillis(),10,"incoming","answered");
    start();loaded();app.session.invalidate();
    long end=SystemClock.elapsedRealtime()+5000;while(!activity.isFinishing()&&!activity.isDestroyed()&&SystemClock.elapsedRealtime()<end)SystemClock.sleep(50);
    assertTrue(activity.isFinishing()||activity.isDestroyed());assertEquals(1,app.store.query("SELECT * FROM calls WHERE id='safe'").size());
  }
  @Test public void foreignHistoryAndWrongLeadResponsesAreRejected() throws Exception {
    JSONObject foreign=history(false);foreign.getJSONArray("phone_calls").getJSONObject(0).put("org_id","other-company");
    json("/api/leads/lead-a/history?page=1&size=20",200,foreign);
    try{CrmHistory.load(app,"lead-a",1);fail("Foreign history");}catch(IOException expected){}
    json("/api/leads/lead-a",200,lead().put("id","other-lead"));
    try{CrmHistory.load(app,"lead-a",1);fail("Wrong lead");}catch(IOException expected){}
  }
  @Test public void missingAndCorruptRecordingsDoNotLeavePlayablePrivateFiles() throws Exception {
    CrmFileReader reader=new CrmFileReader();routes.put("/api/files/recording-a",new Reply(404,"{}".getBytes(StandardCharsets.UTF_8),"application/json",null));
    try{reader.download(app,recording);fail("Missing file");}catch(Api.Failure expected){assertEquals(404,expected.status);}
    byte[] corrupt=wav.clone();corrupt[corrupt.length-1]=1;routes.put("/api/files/recording-a",new Reply(200,corrupt,"audio/wav",null));
    try{reader.download(app,recording);fail("Corrupt file");}catch(IOException expected){}
    assertEquals(0,previews().length);
  }
  @Test public void accountChangeDuringDownloadDiscardsPrivateCopy() throws Exception {
    routes.put("/api/files/recording-a",new Reply(200,wav,"audio/wav",()->app.session.put("user_id","another-caller")));
    try{new CrmFileReader().download(app,recording);fail("Account changed");}catch(IOException expected){}
    assertEquals(0,previews().length);
  }
  @Test public void anotherReaderKeepsTheCurrentProcessPreviewAndOutbox() throws Exception {
    app.store.capture("keep-preview-queue", "+919810001234", "Queued", System.currentTimeMillis(), 10, "incoming", "answered");
    File active = new CrmFileReader().download(app, recording);
    try {
      new CrmFileReader();
      CrmFileReader.clearPreviousProcessPreviews(app);
      assertTrue("A second reader must not remove an active preview", active.isFile());
      assertEquals(wav.length, active.length());
      assertEquals("pending", app.store.query("SELECT state FROM calls WHERE id='keep-preview-queue'").get(0).get("state"));
    } finally { active.delete(); }
  }
  @Test public void oversizedMetadataIsRejectedBeforeFileDownload() throws Exception {
    JSONObject large=new JSONObject(recording.toString()).put("size",SyncPolicy.DEFAULT_RECORDING_LIMIT+1);
    try{new CrmFileReader().download(app,large);fail("Oversized file");}catch(IOException expected){}
    assertTrue(requests.isEmpty());assertEquals(0,previews().length);
  }
  @Test public void trulyEmptySectionsDisplayTheirOwnEmptyStates() throws Exception {
    JSONObject empty=history(false);
    for(String key:new String[]{"phone_calls","manual_calls","notes","tasks","files","activity"}){
      empty.put(key,new JSONArray());empty.getJSONObject("pagination").getJSONObject("totals").put(key,0);
    }
    json("/api/leads/lead-a/history?page=1&size=20",200,empty);start();expect("No synced calls yet");
    find("crm_notes").click();expect("No notes added yet");find("crm_tasks").click();expect("No tasks linked yet");
    find("crm_files").click();expect("No files uploaded yet");
  }
  @Test public void saveFileUsesSelectedDestinationAndAuthenticatedDownload() throws Exception {
    File destination=new File(app.getFilesDir(),"qa-export.wav");destination.delete();
    var instrumentation=InstrumentationRegistry.getInstrumentation();
    IntentFilter filter=new IntentFilter(Intent.ACTION_CREATE_DOCUMENT);filter.addCategory(Intent.CATEGORY_OPENABLE);filter.addDataType("audio/wav");
    var monitor=instrumentation.addMonitor(filter,new Instrumentation.ActivityResult(Activity.RESULT_OK,new Intent().setData(Uri.fromFile(destination))),true);
    try{
      start();loaded();find("crm_files").click();find("crm_save").click();
      expect("File saved to the location you selected.");
      assertArrayEquals(wav,Files.readAllBytes(destination.toPath()));assertTrue(monitor.getHits()>0);assertFalse(app.enabled());assertEquals(0,previews().length);
    }finally{instrumentation.removeMonitor(monitor);destination.delete();}
  }
  private void checkLayout(android.view.View view){
    if(view.isShown() && view.getGlobalVisibleRect(new android.graphics.Rect()) && view instanceof android.widget.TextView text){
      if(view instanceof android.widget.Button)assertTrue("Touch target "+text.getText(),view.getHeight()>=48*view.getResources().getDisplayMetrics().density-1);
      if(text.getLayout()!=null)for(int i=0;i<text.getLayout().getLineCount();i++)assertEquals("Truncated text "+text.getText(),0,text.getLayout().getEllipsisCount(i));
    }
    if(view instanceof android.view.ViewGroup group)for(int i=0;i<group.getChildCount();i++)checkLayout(group.getChildAt(i));
  }
}
