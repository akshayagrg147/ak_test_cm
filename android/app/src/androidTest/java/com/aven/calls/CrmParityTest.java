package com.aven.calls;

import static org.junit.Assert.*;
import android.content.Intent;
import android.os.Bundle;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import androidx.test.uiautomator.*;
import java.io.File;
import okhttp3.*;
import org.json.*;
import org.junit.Test;
import org.junit.runner.RunWith;

/** Uses only the named, disposable emulator workspace after its real call/SAF upload test. */
@RunWith(AndroidJUnit4.class)
public class CrmParityTest {
  private AvenApplication app;
  private UiDevice device;
  private LeadActivity activity;
  private UiObject2 find(int id) throws Exception {
    String name=app.getResources().getResourceEntryName(id),pkg=app.getPackageName();
    if(!device.wait(Until.hasObject(By.res(pkg,name)),1000))
      new UiScrollable(new UiSelector().className("android.widget.ScrollView"))
          .setMaxSearchSwipes(40).scrollIntoView(new UiSelector().resourceId(pkg+":id/"+name));
    UiObject2 item=device.wait(Until.findObject(By.res(pkg,name)),5000);assertNotNull(name,item);
    InstrumentationRegistry.getInstrumentation().runOnMainSync(()->{
      android.view.View view=activity.findViewById(id);
      view.requestRectangleOnScreen(new android.graphics.Rect(0,0,view.getWidth(),view.getHeight()),true);
    });
    device.waitForIdle();return device.findObject(By.res(pkg,name));
  }
  private void expectText(String text) throws Exception {
    if(!device.wait(Until.hasObject(By.text(text)),1000))
      new UiScrollable(new UiSelector().className("android.widget.ScrollView"))
          .setMaxSearchSwipes(40).scrollIntoView(new UiSelector().text(text));
    assertTrue(text,device.wait(Until.hasObject(By.text(text)),5000));
  }
  private void assign(Bundle args,String owner) throws Exception {
    JSONObject body=new JSONObject().put("lead_ids",new JSONArray().put(args.getString("parity_lead_id"))).put("owner_id",owner);
    Request request=new Request.Builder().url(args.getString("server")+"/api/leads/assign")
        .header("X-Requested-With","TalkoCRM").header("Authorization","Bearer "+args.getString("admin_token"))
        .post(RequestBody.create(body.toString(),MediaType.get("application/json"))).build();
    try(Response response=new OkHttpClient().newCall(request).execute()){assertTrue("Fixture assignment",response.isSuccessful());}
  }
  @Test public void sameServerHistoryPlaysAndReassignmentRevokesIt() throws Exception {
    var instrumentation=InstrumentationRegistry.getInstrumentation();
    app=(AvenApplication)instrumentation.getTargetContext().getApplicationContext();
    assertTrue(app.getPackageName().endsWith(".debug"));
    Bundle args=InstrumentationRegistry.getArguments();
    assertNotNull("Provision the disposable parity fixture first",args.getString("parity_lead_id"));
    device=UiDevice.getInstance(instrumentation);app.store.meta("enabled","false");SyncScheduler.cancel(app);app.api.cancelActive();
    SyncEngine.LOCK.lock();try{app.resetLocalData();app.session.clear();}finally{SyncEngine.LOCK.unlock();}
    app.api.login(args.getString("server"),args.getString("phone"),args.getString("password"),"","");
    String original=app.session.get("user_id");
    CrmHistory.Page loaded=CrmHistory.load(app,args.getString("parity_lead_id"),1);
    assertEquals("Emulator QA Customer",loaded.lead().getString("name"));
    JSONObject totals=loaded.history().getJSONObject("pagination").getJSONObject("totals");
    assertTrue(totals.getInt("phone_calls")>0);assertTrue(totals.getInt("files")>0);
    assertEquals(1,totals.getInt("notes"));assertEquals(1,totals.getInt("tasks"));
    assertTrue(loaded.history().getJSONArray("activity").length()>0);
    JSONObject audio=loaded.history().getJSONArray("files").getJSONObject(0);
    activity=(LeadActivity)instrumentation.startActivitySync(new Intent(app,LeadActivity.class)
        .putExtra("lead_id",args.getString("parity_lead_id")).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TASK));
    try {
      assertTrue(device.wait(Until.hasObject(By.res(app.getPackageName(),"crm_summary")),15000));
      find(R.id.crm_notes).click();expectText("Cross-platform QA: Sector 18 corner plot");
      find(R.id.crm_tasks).click();expectText("Cross-platform QA: Arrange Panipat site visit");
      find(R.id.crm_files).click();expectText(audio.getString("name"));find(R.id.crm_play).click();
      assertTrue("Server recording must decode",device.wait(Until.hasObject(By.res(app.getPackageName(),"crm_media_status")
          .text(java.util.regex.Pattern.compile("Playing|Finished"))),15000));
      device.takeScreenshot(new File(app.getExternalFilesDir(null),"qa-parity-player.png"));device.pressBack();
      assertEquals("History must work with an empty local call outbox",0,app.store.query("SELECT * FROM calls").size());
      assign(args,args.getString("parity_second_id"));find(R.id.crm_refresh).click();expectText("History couldn't be loaded");
      assertFalse(device.hasObject(By.text("Emulator QA Customer")));
      try{CrmHistory.load(app,args.getString("parity_lead_id"),1);fail("Reassigned history remained readable");}
      catch(Api.Failure expected){assertEquals(404,expected.status);}
      try{new CrmFileReader().download(app,audio);fail("Reassigned recording remained readable");}
      catch(Api.Failure expected){assertEquals(404,expected.status);}
      device.takeScreenshot(new File(app.getExternalFilesDir(null),"qa-parity-revoked.png"));
    } finally {
      assign(args,original);
      instrumentation.runOnMainSync(activity::finish);app.session.clear();
    }
  }
}
