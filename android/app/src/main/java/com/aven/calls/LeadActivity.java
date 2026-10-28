package com.aven.calls;

import android.app.*;
import android.content.*;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.media.*;
import android.net.Uri;
import android.os.*;
import android.view.*;
import android.widget.*;
import java.io.*;
import java.text.DateFormat;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;

/** Permission-filtered CRM history. This screen never writes to the local call outbox. */
public class LeadActivity extends Activity {
  private static final int INK=0xff193c33, MUTED=0xff59665f, GREEN=0xff20594b, PAPER=0xfff6f6f1;
  private static final int SAVE_FILE=41;
  private final ExecutorService network=Executors.newSingleThreadExecutor();
  private final Handler main=new Handler(Looper.getMainLooper());
  private final CrmFileReader files=new CrmFileReader();
  private final Runnable watch=new Runnable() {
    public void run() {
      if (!valid()) { stopAudio(); finish(); }
      else main.postDelayed(this, 1000);
    }
  };
  private String id, owner, tab="Calls", error="", transfer="";
  private int page=1, generation, mediaGeneration;
  private boolean loading, foreground, fileBusy, resumedBefore;
  private JSONObject lead, history, saving;
  private LinearLayout root;
  private MediaPlayer player;
  private File audioFile;
  private AlertDialog audioDialog;
  private SeekBar seek;
  private TextView audioTime, audioStatus;
  private Button audioToggle;
  private AudioFocusRequest audioFocus;

  private AvenApplication app() { return AvenApplication.get(); }
  private boolean valid() { return app().session.authenticated() && owner.equals(CrmHistory.identity(app())); }
  private int dp(int n) { return Math.round(n*getResources().getDisplayMetrics().density); }

  @Override public void onCreate(Bundle state) {
    super.onCreate(state);
    id=getIntent().getStringExtra("lead_id"); owner=CrmHistory.identity(app());
    if (id==null || !id.matches("[A-Za-z0-9_-]{1,80}") || !valid()) { finish(); return; }
    if (state!=null) {
      tab=state.getString("tab", "Calls"); page=state.getInt("page", 1);
      try { if (state.containsKey("saving")) saving=new JSONObject(state.getString("saving")); }
      catch (JSONException ignored) { }
    }
    if (Build.VERSION.SDK_INT>=33) getOnBackInvokedDispatcher().registerOnBackInvokedCallback(
        android.window.OnBackInvokedDispatcher.PRIORITY_DEFAULT, this::finish);
    fetch();
  }
  @Override protected void onResume() {
    super.onResume(); foreground=true; main.post(watch);
    boolean returning=resumedBefore;resumedBefore=true;
    if(returning && history==null && !loading && !error.isEmpty())fetch();
    else if(history!=null && !loading)render();
  }
  @Override protected void onPause() {
    foreground=false; main.removeCallbacks(watch); cancelPreview();
    super.onPause();
  }
  @Override protected void onDestroy() {
    generation++; mediaGeneration++; main.removeCallbacksAndMessages(null);
    files.cancel(); stopAudio(); network.shutdownNow(); super.onDestroy();
  }
  @Override protected void onSaveInstanceState(Bundle state) {
    state.putString("tab",tab); state.putInt("page",page);
    if (saving!=null) state.putString("saving",saving.toString());
    super.onSaveInstanceState(state);
  }
  private GradientDrawable shape(int color) {
    GradientDrawable d=new GradientDrawable(); d.setColor(color); d.setCornerRadius(dp(12));
    d.setStroke(dp(1),0xffdfe5dd); return d;
  }
  private TextView text(LinearLayout box,String value,int size,boolean bold) {
    TextView t=new TextView(this); t.setText(value); t.setTextSize(size); t.setTextColor(bold?INK:MUTED);
    t.setLineSpacing(dp(3),1); if (bold) t.setTypeface(Typeface.DEFAULT,Typeface.BOLD);
    LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2); lp.bottomMargin=dp(9);
    box.addView(t,lp); return t;
  }
  private Button button(LinearLayout box,String label,int viewId,Runnable action) {
    Button b=new Button(this); b.setId(viewId); b.setText(label); b.setAllCaps(false); b.setTextSize(15);
    b.setTextColor(GREEN); b.setMinHeight(dp(48)); b.setPadding(dp(12),dp(8),dp(12),dp(8));
    b.setStateListAnimator(null); b.setBackground(shape(0xffeaf1e9));
    LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2); lp.setMargins(0,dp(3),0,dp(9));
    box.addView(b,lp); b.setOnClickListener(v->action.run()); return b;
  }
  private LinearLayout card() {
    LinearLayout box=new LinearLayout(this); box.setOrientation(LinearLayout.VERTICAL);
    box.setPadding(dp(16),dp(16),dp(16),dp(9)); box.setBackground(shape(Color.WHITE));
    LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2); lp.bottomMargin=dp(14);
    root.addView(box,lp); return box;
  }
  private void render() {
    if (isFinishing() || isDestroyed()) return;
    LinearLayout shell=new LinearLayout(this); shell.setOrientation(LinearLayout.VERTICAL); shell.setBackgroundColor(PAPER);
    LinearLayout header=new LinearLayout(this); header.setOrientation(LinearLayout.VERTICAL);
    header.setPadding(dp(20),dp(6),dp(20),0); shell.addView(header);
    button(header,"‹  Back to leads",R.id.crm_back,this::finish);
    text(header,lead==null?"Lead details":lead.optString("name"),23,true).setId(R.id.crm_lead_name);
    if (lead!=null) text(header,lead.optString("phone"),15,false);
    LinearLayout tabRows=new LinearLayout(this);tabRows.setOrientation(LinearLayout.VERTICAL);
    tabRows.setPadding(dp(16),0,dp(16),0);shell.addView(tabRows);
    int columns=getResources().getConfiguration().fontScale>1.2f?3:5;
    LinearLayout tabs=null;
    String[] labels={"Calls","Notes","Activity","Tasks","Files"};
    int[] ids={R.id.crm_calls,R.id.crm_notes,R.id.crm_activity,R.id.crm_tasks,R.id.crm_files};
    for (int i=0;i<labels.length;i++) {
      if(i%columns==0){tabs=new LinearLayout(this);tabRows.addView(tabs);}
      String label=labels[i]; Button b=button(tabs,label,ids[i],()->{
        if (!tab.equals(label)) { cancelPreview(); tab=label; if(page!=1){page=1;fetch();}else render(); }
      });
      b.setSelected(tab.equals(label)); b.setTextColor(tab.equals(label)?Color.WHITE:GREEN);
      b.setBackground(shape(tab.equals(label)?GREEN:0xffeaf1e9));
      b.setPadding(dp(4),dp(8),dp(4),dp(8));b.setTextSize(14);
      LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,-2,1); lp.setMargins(dp(2),0,dp(2),dp(8)); b.setLayoutParams(lp);
    }
    if(labels.length%columns!=0 && tabs!=null)for(int i=labels.length%columns;i<columns;i++)tabs.addView(new View(this),new LinearLayout.LayoutParams(0,dp(1),1));
    ScrollView scroll=new ScrollView(this); scroll.setFillViewport(true);
    root=new LinearLayout(this); root.setId(R.id.crm_content); root.setOrientation(LinearLayout.VERTICAL);
    root.setPadding(dp(20),dp(12),dp(20),dp(24)); scroll.addView(root);
    shell.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
    if (loading) text(card(),"Loading CRM history…",17,true);
    else if (!error.isEmpty()) {
      LinearLayout box=card(); text(box,"History couldn't be loaded",18,true); text(box,error,15,false);
      button(box,"Try again",R.id.crm_retry,this::fetch);
    } else if (history!=null) {
      LinearLayout tools=card();
      text(tools,"Saved in your company CRM",15,true);
      text(tools,totals("phone_calls")+(totals("phone_calls")==1?" synced call · ":" synced calls · ")
          +totals("files")+(totals("files")==1?" file":" files"),14,false).setId(R.id.crm_summary);
      if (lead.optBoolean("dnd")) text(tools,"Do not call",15,true);
      else button(tools,"Call lead",R.id.crm_dial,()->{
        try { startActivity(new Intent(Intent.ACTION_DIAL,Uri.parse("tel:"+lead.optString("phone")))); }
        catch (ActivityNotFoundException e) { showMessage("No Phone app is available."); }
      });
      button(tools,"Refresh history",R.id.crm_refresh,this::fetch);
      if (fileBusy || !transfer.isEmpty()) text(tools,transfer,15,false).setId(R.id.crm_transfer);
      int pages=pages();
      text(root,tab+" · Page "+page+" of "+pages,15,true).setId(R.id.crm_page);
      if (pages>1) {
        LinearLayout nav=new LinearLayout(this); root.addView(nav);
        Button prev=button(nav,"Newer",R.id.crm_previous,()->{page--;fetch();});
        Button next=button(nav,"Older",R.id.crm_next,()->{page++;fetch();});
        for (Button b:new Button[]{prev,next}) { LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,-2,1);lp.setMargins(dp(3),0,dp(3),dp(8));b.setLayoutParams(lp); }
        prev.setEnabled(page>1);next.setEnabled(page<pages);
      }
      switch(tab) {
        case "Calls" -> calls();
        case "Notes" -> notes();
        case "Activity" -> activity();
        case "Tasks" -> tasks();
        case "Files" -> attachments();
        default -> { }
      }
    }
    setContentView(shell);
    shell.setOnApplyWindowInsetsListener((v,insets)->{
      shell.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom()); return insets;
    });shell.requestApplyInsets();
  }
  private int totals(String key) { return history.optJSONObject("pagination").optJSONObject("totals").optInt(key); }
  private int pages() {
    int total=switch(tab){case "Calls"->Math.max(totals("phone_calls"),totals("manual_calls"));case "Notes"->totals("notes");case "Activity"->totals("activity");case "Tasks"->totals("tasks");default->totals("files");};
    return Math.max(1,(total+19)/20);
  }
  private JSONArray items(String key) { return history.optJSONArray(key); }
  private String who(JSONObject item,String key) {
    JSONObject people=history.optJSONObject("people"); return people==null?"Team member":people.optString(item.optString(key),"Team member");
  }
  private String date(String value) {
    try{return DateFormat.getDateTimeInstance(DateFormat.MEDIUM,DateFormat.SHORT).format(Date.from(Instant.parse(value)));}
    catch(Exception ignored){return "Date unavailable";}
  }
  private void calls() {
    text(root,"Synced phone calls ("+totals("phone_calls")+")",18,true);
    JSONArray calls=items("phone_calls");
    if(calls.length()==0) text(card(),totals("phone_calls")==0?"No synced calls yet":"No more synced calls on this page",16,false);
    for(int i=0;i<calls.length();i++) {
      JSONObject c=calls.optJSONObject(i); LinearLayout box=card();
      text(box,EstateFormat.label(c.optString("direction"))+" · "+EstateFormat.label(c.optString("result")),17,true);
      text(box,date(c.optString("started_at"))+" · "+EstateFormat.duration(c.optString("duration")),15,false);
      text(box,who(c,"user_id"),14,false);
      JSONArray recordings=c.optJSONArray("recordings");
      if(recordings==null || recordings.length()==0) text(box,"No recording attached",14,false);
      else for(int j=0;j<recordings.length();j++) file(box,recordings.optJSONObject(j),false);
    }
    text(root,"Manual call outcomes ("+totals("manual_calls")+")",18,true);
    JSONArray manual=items("manual_calls");
    if(manual.length()==0) text(card(),totals("manual_calls")==0?"No manual outcomes yet":"No more manual outcomes on this page",16,false);
    for(int i=0;i<manual.length();i++) {
      JSONObject c=manual.optJSONObject(i); LinearLayout box=card();
      text(box,EstateFormat.label(c.optString("outcome")),17,true);
      text(box,c.optString("notes").isBlank()?"No call notes added.":c.optString("notes"),16,false);
      text(box,date(c.optString("created_at"))+" · "+EstateFormat.duration(c.optString("duration"))+" declared · "+who(c,"user_id"),14,false);
    }
  }
  private void notes() {
    if(page==1 && !lead.optString("notes").isBlank()) {LinearLayout box=card();text(box,"Lead notes",17,true);text(box,lead.optString("notes"),16,false);}
    JSONArray notes=items("notes");
    if(notes.length()==0) text(card(),totals("notes")==0?"No notes added yet":"No more notes on this page",16,false);
    for(int i=0;i<notes.length();i++) {JSONObject n=notes.optJSONObject(i);LinearLayout box=card();text(box,n.optString("text"),16,true);text(box,who(n,"author_id")+" · "+date(n.optString("created_at")),14,false);}
  }
  private void activity() {
    JSONArray records=items("activity");
    if(records.length()==0) text(card(),"No activity on this page",16,false);
    for(int i=0;i<records.length();i++) {JSONObject a=records.optJSONObject(i);LinearLayout box=card();text(box,a.optString("summary"),16,true);text(box,who(a,"actor_id")+" · "+date(a.optString("created_at")),14,false);}
  }
  private void tasks() {
    JSONArray records=items("tasks");
    if(records.length()==0) text(card(),totals("tasks")==0?"No tasks linked yet":"No more tasks on this page",16,false);
    for(int i=0;i<records.length();i++) {JSONObject t=records.optJSONObject(i);LinearLayout box=card();text(box,t.optString("title"),17,true);text(box,EstateFormat.label(t.optString("state"))+" · Due "+date(t.optString("due_at")),15,false);if(!t.optString("description").isBlank())text(box,t.optString("description"),15,false);}
  }
  private void attachments() {
    JSONArray records=items("files");
    if(records.length()==0)text(card(),totals("files")==0?"No files uploaded yet":"No more files on this page",16,false);
    for(int i=0;i<records.length();i++)file(card(),records.optJSONObject(i),true);
  }
  private void file(LinearLayout box,JSONObject f,boolean allowSave) {
    text(box,f.optString("name","Recording"),15,true);
    text(box,Math.max(1,(f.optLong("size")+1023)/1024)+" KB · "+date(f.optString("created_at")),13,false);
    if(f.optString("mime").startsWith("audio/")) {
      Button play=button(box,"Play recording",R.id.crm_play,()->play(f));
      play.setContentDescription("Play "+f.optString("name"));play.setEnabled(!fileBusy);
    }
    if(allowSave) {
      Button save=button(box,"Save file",R.id.crm_save,()->{
        saving=f;
        Intent intent=new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
            .setType(f.optString("mime","application/octet-stream")).putExtra(Intent.EXTRA_TITLE,f.optString("name","CRM file"));
        try{startActivityForResult(intent,SAVE_FILE);}catch(ActivityNotFoundException e){saving=null;showMessage("No file picker is available.");}
      });save.setContentDescription("Save "+f.optString("name"));save.setEnabled(!fileBusy);
    }
  }
  private void fetch() {
    if(!valid()){finish();return;}cancelPreview();
    int request=++generation, requestedPage=page;loading=true;error="";history=null;render();
    network.submit(()->{
      try {
        CrmHistory.Page result=CrmHistory.load(app(),id,requestedPage);
        main.post(()->{if(request!=generation || isDestroyed())return;if(!valid()){finish();return;}lead=result.lead();history=result.history();loading=false;if(page>pages()){page=pages();fetch();}else render();});
      }catch(Exception e){main.post(()->{
        if(request!=generation || isDestroyed())return;loading=false;
        if(!valid()){finish();return;}
        if(e instanceof Api.Failure failure && (failure.status==403 || failure.status==404))lead=null;
        if(e instanceof Api.Failure failure && failure.status==404 && failure.code.equals("not_found"))
          error="This lead is no longer available to your account. Return to Leads and refresh your assignments.";
        else if(e instanceof Api.Failure failure && failure.status==403 && failure.code.equals("organization_suspended"))
          error="Your company account is suspended. Contact your administrator.";
        else if(e instanceof Api.Failure failure && failure.status==403 && failure.code.equals("permission_denied"))
          error="Your account cannot access this lead. Contact your administrator.";
        else error="Check your connection and tap Try again. Your calls remain saved in the CRM.";
        render();
      });}
    });
  }
  private void showMessage(String message){new AlertDialog.Builder(this).setMessage(message).setPositiveButton("OK",null).show();}
  private void play(JSONObject f) {
    if(fileBusy || !valid())return; stopAudio(); int request=++mediaGeneration;fileBusy=true;transfer="Loading recording…";render();
    network.submit(()->{
      File downloaded=null;
      try {
        downloaded=files.download(app(),f);File ready=downloaded;
        main.post(()->{
          if(!foreground || !valid() || request!=mediaGeneration || isDestroyed()){ready.delete();return;}
          fileBusy=false;transfer="";
          render();openPlayer(ready,f.optString("name","Recording"));
        });
      }catch(Exception e){if(downloaded!=null)downloaded.delete();main.post(()->{
        if(request!=mediaGeneration)return;
        fileBusy=false;transfer="";
        if(foreground && !isDestroyed() && request==mediaGeneration){render();showMessage(e instanceof Api.Failure?e.getMessage():"Recording couldn't be loaded. Refresh the lead and try again.");}
      });}
    });
  }
  private void openPlayer(File source,String name) {
    audioFile=source;
    LinearLayout box=new LinearLayout(this);box.setPadding(dp(20),dp(12),dp(20),dp(8));box.setOrientation(LinearLayout.VERTICAL);
    text(box,name,15,true);audioStatus=text(box,"Preparing audio…",15,false);audioStatus.setId(R.id.crm_media_status);
    audioTime=text(box,"0:00",14,false);audioTime.setId(R.id.crm_media_time);
    seek=new SeekBar(this);seek.setId(R.id.crm_seek);seek.setContentDescription("Recording position");box.addView(seek);
    audioToggle=button(box,"Pause",R.id.crm_audio_toggle,()->{
      if(player==null)return;
      if(player.isPlaying()){player.pause();audioStatus.setText(R.string.crm_paused);audioToggle.setText(R.string.crm_audio_play);}
      else{if(player.getCurrentPosition()>=player.getDuration())player.seekTo(0);startPlayback();}
    });audioToggle.setEnabled(false);
    ScrollView audioContent=new ScrollView(this);audioContent.addView(box);
    audioDialog=new AlertDialog.Builder(this).setTitle("Call recording").setView(audioContent).setNegativeButton("Close",null).create();
    audioDialog.setOnDismissListener(d->stopAudio());audioDialog.show();
    try {
      player=new MediaPlayer();
      player.setAudioAttributes(new AudioAttributes.Builder().setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).setUsage(AudioAttributes.USAGE_MEDIA).build());
      player.setDataSource(source.getAbsolutePath());
      player.setOnPreparedListener(p->{
        if(!foreground || !valid()){stopAudio();return;}
        seek.setMax(p.getDuration());audioToggle.setEnabled(true);startPlayback();tick();
      });
      player.setOnCompletionListener(p->{audioStatus.setText(R.string.crm_finished);audioToggle.setText(R.string.crm_play_again);});
      player.setOnErrorListener((p,what,extra)->{audioStatus.setText(R.string.crm_audio_unavailable);audioToggle.setEnabled(false);return true;});
      seek.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener(){
        public void onProgressChanged(SeekBar bar,int progress,boolean user){if(user && player!=null && audioToggle.isEnabled())player.seekTo(progress);}
        public void onStartTrackingTouch(SeekBar bar){} public void onStopTrackingTouch(SeekBar bar){}
      });
      player.prepareAsync();
    }catch(Exception e){audioStatus.setText(R.string.crm_audio_unavailable);audioToggle.setEnabled(false);}
  }
  private final Runnable progress=new Runnable(){public void run(){tick();}};
  private void startPlayback(){
    AudioManager manager=(AudioManager)getSystemService(AUDIO_SERVICE);
    if(audioFocus==null)audioFocus=new AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT)
        .setAudioAttributes(new AudioAttributes.Builder().setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).setUsage(AudioAttributes.USAGE_MEDIA).build())
        .setWillPauseWhenDucked(true).setOnAudioFocusChangeListener(change->{
          if(change<0 && player!=null && player.isPlaying()){player.pause();audioStatus.setText(R.string.crm_paused);audioToggle.setText(R.string.crm_audio_play);}
        },main).build();
    if(manager.requestAudioFocus(audioFocus)==AudioManager.AUDIOFOCUS_REQUEST_GRANTED){player.start();audioStatus.setText(R.string.crm_playing);audioToggle.setText(R.string.crm_pause);}
    else{audioStatus.setText(R.string.crm_audio_busy);audioToggle.setText(R.string.crm_audio_play);}
  }
  private void tick(){
    if(player==null || audioToggle==null || !audioToggle.isEnabled())return;
    int at=player.getCurrentPosition(),total=player.getDuration();seek.setProgress(at);
    audioTime.setText(getString(R.string.crm_recording_time,EstateFormat.duration(String.valueOf(at/1000)),EstateFormat.duration(String.valueOf(total/1000))));
    main.postDelayed(progress,500);
  }
  private void stopAudio(){
    main.removeCallbacks(progress);
    if(audioFocus!=null){((AudioManager)getSystemService(AUDIO_SERVICE)).abandonAudioFocusRequest(audioFocus);audioFocus=null;}
    if(player!=null){player.release();player=null;}
    if(audioDialog!=null){AlertDialog d=audioDialog;audioDialog=null;d.setOnDismissListener(null);d.dismiss();}
    if(audioFile!=null){audioFile.delete();audioFile=null;}
  }
  private void cancelPreview(){mediaGeneration++;files.cancel();fileBusy=false;transfer="";stopAudio();}
  @Override protected void onActivityResult(int request,int result,Intent data){
    super.onActivityResult(request,result,data);
    if(request!=SAVE_FILE)return;
    JSONObject selected=saving;saving=null;
    if(result!=RESULT_OK || data==null || data.getData()==null || selected==null || !valid())return;
    Uri destination=data.getData();fileBusy=true;transfer="Saving file…";render();
    network.submit(()->{
      File temp=null;String message;
      try{
        temp=files.download(app(),selected);CrmHistory.check(app(),owner);
        try(InputStream in=new FileInputStream(temp);OutputStream out=getContentResolver().openOutputStream(destination,"wt")){
          if(out==null)throw new IOException("Destination unavailable");byte[] bytes=new byte[16384];int n;
          while((n=in.read(bytes))!=-1){CrmHistory.check(app(),owner);out.write(bytes,0,n);}
        }message="File saved to the location you selected.";
      }catch(Exception e){message="File couldn't be saved. Check your connection and try again.";}
      finally{if(temp!=null)temp.delete();}
      String outcome=message;main.post(()->{fileBusy=false;transfer=outcome;if(!isDestroyed() && valid())render();});
    });
  }
}
