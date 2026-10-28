package com.aven.calls;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.database.*;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.*;
import android.provider.*;
import android.text.InputType;
import android.text.Editable;
import android.text.TextWatcher;
import android.text.method.PasswordTransformationMethod;
import android.view.inputmethod.EditorInfo;
import android.view.*;
import android.widget.*;
import java.text.DateFormat;
import java.util.*;
import java.util.concurrent.*;
import org.json.JSONObject;

public class MainActivity extends Activity {
  private static String stateLabel(String state) {
    return switch (state) {
      case "pending", "queued" -> "Waiting to upload";
      case "synced", "uploaded" -> "Saved to CRM";
      case "waiting" -> "Waiting for file";
      case "unavailable" -> "No audio expected";
      case "too_large" -> "File too large";
      case "missing" -> "Select file again";
      case "ambiguous", "error", "review" -> "Needs review";
      case "excluded", "blocked" -> "Access changed";
      default -> state;
    };
  }

  private static final int PERMISSIONS = 10, FOLDER = 11, AUDIO = 12;
  private static final int INK = 0xff193c33, MUTED = 0xff59665f, BLUE = 0xff20594b;
  private static final int PAPER = 0xfff6f6f1, LINE = 0xffdfe5dd, SOFT = 0xffeaf1e9;
  private final ExecutorService executor = Executors.newSingleThreadExecutor();
  private final Handler main = new Handler(Looper.getMainLooper());
  private LinearLayout root, recent, contacts;
  private TextView status, summary, folderStatus, uploadHeading, customerCount, waitingCount, todayCount;
  private EditText server, phone, password, code, callingCode;
  private CheckBox consent;
  private String challenge = "", selectedCall = "", listFingerprint = "";
  private boolean busy = false;
  private boolean renderedAuthenticated = false;
  private String page = "home", customerQuery = "", notice = "", setupFingerprint = "";
  private String callFilter = "all";
  private boolean leadsLoading;
  private String leadsError = "";
  private long leadsAttemptAt;
  private TextView leadStatus;
  private Button refreshLeadsButton;
  private long noticeUntil;
  private boolean connectionExpanded = false;
  private ContentObserver observer;
  private final Runnable poll =
      new Runnable() {
        @Override
        public void run() {
          if (!isFinishing()) {
            if (app().session.authenticated() != renderedAuthenticated) {
              challenge = "";
              code = null;
              page = "home";
              render();
            } else if (renderedAuthenticated && !setupState().equals(setupFingerprint)) {
              render();
            } else refreshDashboard();
            main.postDelayed(this, 3000);
          }
        }
      };

  private AvenApplication app() {
    return AvenApplication.get();
  }

  private int dp(float value) {
    return Math.round(value * getResources().getDisplayMetrics().density);
  }

  @Override
  public void onCreate(Bundle saved) {
    super.onCreate(saved);
    CrmFileReader.clearPreviousProcessPreviews(app());
    if (saved != null) {
      challenge = saved.getString("challenge", "");
      selectedCall = saved.getString("selectedCall", "");
      page = saved.getString("page", "home");
      customerQuery = saved.getString("customerQuery", "");
      connectionExpanded = saved.getBoolean("connectionExpanded", false);
      callFilter = saved.getString("callFilter", "all");
    }
    render();
    if (Build.VERSION.SDK_INT >= 33)
      getOnBackInvokedDispatcher().registerOnBackInvokedCallback(
          android.window.OnBackInvokedDispatcher.PRIORITY_DEFAULT, this::goBack);
  }

  @Override
  protected void onSaveInstanceState(Bundle state) {
    state.putString("challenge", challenge);
    state.putString("selectedCall", selectedCall);
    state.putString("page", page);
    state.putString("customerQuery", customerQuery);
    state.putBoolean("connectionExpanded", connectionExpanded);
    state.putString("callFilter", callFilter);
    super.onSaveInstanceState(state);
  }

  @Override
  protected void onResume() {
    super.onResume();
    main.removeCallbacks(poll);
    main.post(poll);
    registerObserver();
    refreshLeads(false);
    if (app().enabled()) SyncScheduler.capture(this, 1);
  }

  @Override
  protected void onPause() {
    main.removeCallbacks(poll);
    if (observer != null) {
      getContentResolver().unregisterContentObserver(observer);
      observer = null;
    }
    super.onPause();
  }

  @Override
  protected void onDestroy() {
    main.removeCallbacksAndMessages(null);
    executor.shutdownNow();
    super.onDestroy();
  }

  private void registerObserver() {
    if (observer != null
        || checkSelfPermission(Manifest.permission.READ_CALL_LOG)
            != PackageManager.PERMISSION_GRANTED) return;
    observer =
        new ContentObserver(main) {
          @Override
          public void onChange(boolean self) {
            SyncScheduler.capture(MainActivity.this, 2);
          }
        };
    try {
      getContentResolver().registerContentObserver(CallLog.Calls.CONTENT_URI, true, observer);
    } catch (SecurityException ignored) {
      observer = null;
    }
  }

  private void render() {
    recent = contacts = null;
    leadStatus = null;
    refreshLeadsButton = null;
    status = summary = folderStatus = uploadHeading = customerCount = waitingCount = todayCount = null;
    callingCode = null;
    consent = null;
    listFingerprint = "";
    renderedAuthenticated = app().session.authenticated();
    setupFingerprint = setupState();
    LinearLayout shell = new LinearLayout(this);
    shell.setOrientation(LinearLayout.VERTICAL);
    shell.setBackgroundColor(PAPER);
    LinearLayout brand = new LinearLayout(this);
    brand.setGravity(Gravity.CENTER_VERTICAL);
    brand.setPadding(dp(20), dp(10), dp(20), dp(10));
    ImageView mark = new ImageView(this);
    mark.setImageResource(R.drawable.ic_aven);
    mark.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
    mark.setPadding(dp(7), dp(7), dp(7), dp(7));
    mark.setBackground(rounded(SOFT, 0, 12));
    brand.addView(mark, new LinearLayout.LayoutParams(dp(42), dp(42)));
    TextView brandName = new TextView(this);
    brandName.setText("Aven Realty");
    brandName.setTextSize(20);
    brandName.setTextColor(INK);
    brandName.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
    brandName.setPadding(dp(10), 0, 0, 0);
    LinearLayout brandWords = new LinearLayout(this);
    brandWords.setOrientation(LinearLayout.VERTICAL);
    brandWords.addView(brandName);
    TextView company = new TextView(this);
    company.setText(renderedAuthenticated ? app().session.get("org_name") : "Your real-estate workspace");
    company.setTextSize(13);
    company.setTextColor(MUTED);
    company.setMaxLines(2);
    company.setPadding(dp(10), 0, dp(8), 0);
    brandWords.addView(company);
    brand.addView(brandWords, new LinearLayout.LayoutParams(0, -2, 1));
    shell.addView(brand);
    root = new LinearLayout(this);
    root.setOrientation(LinearLayout.VERTICAL);
    root.setPadding(dp(20), dp(8), dp(20), dp(24));
    ScrollView scroll = new ScrollView(this);
    scroll.setFillViewport(true);
    scroll.addView(root);
    shell.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
    if (!renderedAuthenticated) loginScreen();
    else {
      dashboard();
      LinearLayout navigation = new LinearLayout(this);
      navigation.setPadding(dp(12), dp(6), dp(12), dp(6));
      navigation.setBackgroundColor(Color.WHITE);
      nav(navigation, "Home", "home", R.id.nav_home);
      nav(navigation, "Leads", "customers", R.id.nav_customers);
      nav(navigation, "Calls", "calls", R.id.nav_calls);
      nav(navigation, "More", "settings", R.id.nav_settings);
      shell.addView(navigation);
    }
    setContentView(shell);
    shell.setOnApplyWindowInsetsListener(
        (view, insets) -> {
          int top = insets.getSystemWindowInsetTop(), bottom = insets.getSystemWindowInsetBottom();
          shell.setPadding(insets.getSystemWindowInsetLeft(), top,
              insets.getSystemWindowInsetRight(), bottom);
          return insets;
        });
    shell.requestApplyInsets();
  }

  private void nav(LinearLayout parent, String label, String target, int id) {
    TextView item = new TextView(this);
    item.setId(id);
    item.setText(label);
    item.setTextSize(14);
    item.setGravity(Gravity.CENTER);
    item.setMinHeight(dp(52));
    item.setPadding(dp(2), dp(6), dp(2), dp(6));
    int icon = switch (target) {
      case "customers" -> R.drawable.ic_leads;
      case "calls" -> R.drawable.ic_calls;
      case "settings" -> R.drawable.ic_settings;
      default -> R.drawable.ic_home;
    };
    android.graphics.drawable.Drawable glyph = getDrawable(icon).mutate();
    glyph.setTint(page.equals(target) ? BLUE : MUTED);
    glyph.setBounds(0, 0, dp(22), dp(22));
    item.setCompoundDrawables(null, glyph, null, null);
    item.setCompoundDrawablePadding(dp(3));
    item.setSelected(page.equals(target));
    item.setTextColor(page.equals(target) ? BLUE : MUTED);
    item.setTypeface(Typeface.DEFAULT, page.equals(target) ? Typeface.BOLD : Typeface.NORMAL);
    item.setBackground(rounded(page.equals(target) ? SOFT : Color.WHITE, 0, 12));
    item.setFocusable(true);
    item.setOnClickListener(v -> {
      if (!busy) {
        hideKeyboard(); page = target; render();
        if (target.equals("customers")) refreshLeads(false);
      }
    });
    parent.addView(item, new LinearLayout.LayoutParams(0, -2, 1));
  }

  private GradientDrawable rounded(int color, int stroke, int radius) {
    GradientDrawable shape = new GradientDrawable();
    shape.setColor(color);
    shape.setCornerRadius(dp(radius));
    if (stroke != 0) shape.setStroke(dp(1), stroke);
    return shape;
  }

  private boolean callAccess() {
    return checkSelfPermission(Manifest.permission.READ_CALL_LOG) == PackageManager.PERMISSION_GRANTED
        && checkSelfPermission(Manifest.permission.READ_PHONE_STATE) == PackageManager.PERMISSION_GRANTED;
  }

  private boolean recordingFolderReady() {
    String tree = app().store.meta("recording_tree");
    if (tree.isEmpty() || app().store.meta("folder_status").contains("access was removed")) return false;
    return getContentResolver().getPersistedUriPermissions().stream()
        .anyMatch(p -> p.isReadPermission() && p.getUri().toString().equals(tree));
  }

  private String setupState() {
    return app().enabled() + ":" + callAccess() + ":" + recordingFolderReady()
        + ":" + app().store.meta("recording_setup_skipped");
  }

  private void notice(String message) {
    notice = message;
    noticeUntil = System.currentTimeMillis() + 12000;
    if (status != null) {
      status.setVisibility(View.VISIBLE);
      status.setText(message);
      status.announceForAccessibility(message);
    }
  }

  private void hideKeyboard() {
    View focused = getCurrentFocus();
    if (focused != null) {
      android.view.inputmethod.InputMethodManager keyboard =
          (android.view.inputmethod.InputMethodManager) getSystemService(INPUT_METHOD_SERVICE);
      if (keyboard != null) keyboard.hideSoftInputFromWindow(focused.getWindowToken(), 0);
      focused.clearFocus();
    }
  }

  private LinearLayout card(String title) {
    LinearLayout box = new LinearLayout(this);
    box.setOrientation(LinearLayout.VERTICAL);
    box.setPadding(dp(18), dp(17), dp(18), dp(12));
    GradientDrawable bg = new GradientDrawable();
    bg.setColor(Color.WHITE);
    bg.setCornerRadius(dp(18));
    bg.setStroke(dp(1), LINE);
    box.setBackground(bg);
    LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2);
    lp.topMargin = dp(16);
    root.addView(box, lp);
    if (!title.isEmpty()) text(box, title, 18, true, INK);
    return box;
  }

  private TextView text(LinearLayout parent, String value, int size, boolean bold, int color) {
    TextView view = new TextView(this);
    view.setText(value);
    view.setTextSize(size);
    view.setTextColor(color);
    view.setTextDirection(View.TEXT_DIRECTION_FIRST_STRONG);
    view.setLineSpacing(dp(3), 1);
    if (bold) view.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
    LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2);
    lp.bottomMargin = dp(10);
    parent.addView(view, lp);
    return view;
  }

  private EditText input(LinearLayout parent, String label, int type, String value, int id) {
    TextView caption = text(parent, label, 15, true, INK);
    EditText field = new EditText(this);
    field.setId(id);
    caption.setLabelFor(id);
    field.setContentDescription(label);
    field.setTextSize(16);
    field.setTextColor(INK);
    field.setHintTextColor(MUTED);
    field.setSingleLine(true);
    field.setInputType(type);
    field.setText(value);
    field.setMinHeight(dp(48));
    field.setPadding(dp(12), dp(10), dp(12), dp(10));
    field.setBackground(rounded(PAPER, LINE, 10));
    LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2);
    lp.bottomMargin = dp(14);
    parent.addView(field, lp);
    return field;
  }

  private Button button(LinearLayout parent, String label, boolean primary, Runnable action) {
    Button view = new Button(this);
    view.setText(label);
    view.setTextSize(16);
    view.setAllCaps(false);
    view.setStateListAnimator(null);
    view.setMinHeight(dp(48));
    view.setPadding(dp(12), dp(8), dp(12), dp(8));
    view.setTextColor(primary ? Color.WHITE : BLUE);
    GradientDrawable bg = new GradientDrawable();
    bg.setCornerRadius(dp(10));
    bg.setColor(primary ? BLUE : SOFT);
    bg.setStroke(dp(1), primary ? BLUE : LINE);
    view.setBackground(bg);
    LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2);
    lp.topMargin = dp(5);
    lp.bottomMargin = dp(10);
    parent.addView(view, lp);
    view.setOnClickListener(
        v -> {
          if (!busy) action.run();
        });
    return view;
  }

  private void loginScreen() {
    text(root, challenge.isEmpty() ? "Move every enquiry forward." : "Verify your sign-in", 25, true, INK);
    text(root, "Your property leads, conversations and call recordings. Together.", 16, false, MUTED);
    LinearLayout box = card(challenge.isEmpty() ? "Your work account" : "Verify your sign-in");
    if (!app().session.get("user_id").isEmpty())
      text(
          box,
          "Sign in again to continue your saved work. Choosing a different account removes"
              + " calls still waiting on this phone.",
          14,
          false,
          MUTED);
    text(
        box,
        "Use the account phone number and password your manager gave you.",
        15,
        false,
        MUTED);
    String initial = app().session.get("server");
    if (initial.isEmpty()) initial = BuildConfig.DEFAULT_SERVER_URL;
    if (initial.isEmpty()) connectionExpanded = true;
    LinearLayout connectionBox = new LinearLayout(this);
    connectionBox.setOrientation(LinearLayout.VERTICAL);
    server =
        input(
            connectionBox,
            "Workspace address",
            InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI,
            initial,
            R.id.server_address);
    text(connectionBox, "Only change this if your manager gives you a new address.", 14, false, MUTED);
    phone = input(box, "Account phone number", InputType.TYPE_CLASS_PHONE, "", R.id.login_phone);
    phone.setImeOptions(EditorInfo.IME_ACTION_NEXT);
    password =
        input(
            box,
            "Password",
            InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD,
            "",
            R.id.login_password);
    password.setImeOptions(EditorInfo.IME_ACTION_DONE);
    CheckBox showPassword = new CheckBox(this);
    showPassword.setText("Show password");
    showPassword.setTextSize(14);
    showPassword.setTextColor(MUTED);
    showPassword.setMinHeight(dp(44));
    box.addView(showPassword);
    showPassword.setOnCheckedChangeListener((v, checked) -> {
      password.setTransformationMethod(checked ? null : PasswordTransformationMethod.getInstance());
      password.setSelection(password.length());
    });
    if (!challenge.isEmpty())
      code = input(box, "Authenticator code", InputType.TYPE_CLASS_NUMBER, "", R.id.login_code);
    status = text(box, "", 15, false, MUTED);
    status.setId(R.id.sync_status);
    Button submit = button(
        box,
        challenge.isEmpty() ? "Sign in" : "Verify and sign in",
        true,
        () -> {
          final String address;
          try {
            address = Endpoint.validate(server.getText().toString(), BuildConfig.DEBUG);
          } catch (IllegalArgumentException e) {
            connectionExpanded = true;
            connectionBox.setVisibility(View.VISIBLE);
            notice(e.getMessage());
            return;
          }
          String number = phone.getText().toString(),
              secret = password.getText().toString(),
              otp = code == null ? "" : code.getText().toString();
          if (number.isBlank() || secret.isBlank()) {
            notice("Enter your account phone number and password.");
            return;
          }
          run(
              "Signing in…",
              () -> {
                SyncEngine.LOCK.lockInterruptibly();
                try {
                  return app().api.login(address, number, secret, challenge, otp);
                } finally {
                  SyncEngine.LOCK.unlock();
                }
              },
              value -> {
                hideKeyboard();
                if (value.optBoolean("challenge_required")) {
                  challenge = value.optString("challenge");
                  code = null;
                  render();
                  server.setText(address);
                  phone.setText(number);
                  password.setText(secret);
                  status.setText(
                      "Enter the current code from your authenticator, then sign in again.");
                  code.post(() -> {
                    if (code != null && !isDestroyed()) {
                      code.requestFocus();
                      code.requestRectangleOnScreen(
                          new android.graphics.Rect(0, 0, code.getWidth(), code.getHeight()), true);
                    }
                  });
                } else {
                  password.setText("");
                  challenge = "";
                  code = null;
                  page = "home";
                  render();
                  refreshLeads(true);
                  SyncScheduler.restore(this);
                  SyncScheduler.capture(this, 0);
                }
              });
        });
    submit.setId(R.id.login_submit);
    password.setOnEditorActionListener((v, action, event) -> {
      if (action == EditorInfo.IME_ACTION_DONE) { submit.performClick(); return true; }
      return false;
    });
    if (!challenge.isEmpty())
      button(
          box,
          "Restart sign-in",
          false,
          () -> {
            String address = server.getText().toString(), number = phone.getText().toString();
            challenge = "";
            code = null;
            render();
            server.setText(address);
            phone.setText(number);
          });
    button(box, "Connection settings", false, () -> {
      connectionExpanded = !connectionExpanded;
      connectionBox.setVisibility(connectionExpanded ? View.VISIBLE : View.GONE);
    }).setId(R.id.connection_settings);
    box.addView(connectionBox);
    connectionBox.setVisibility(connectionExpanded ? View.VISIBLE : View.GONE);
    text(root, "Need an account? Ask your manager for your sign-in details.", 14, false, MUTED);
  }

  private void dashboard() {
    if (page.equals("customers")) customersScreen();
    else if (page.equals("calls")) callsScreen();
    else if (page.equals("settings")) settingsScreen();
    else homeScreen();
    refreshDashboard();
  }

  private void homeScreen() {
    String name = app().session.get("name").trim();
    text(root, "Hello, " + (name.isEmpty() ? "there" : name.split("\\s+")[0]), 24, true, INK);
    text(root, "A clear view of your property conversations.", 15, false, MUTED);
    LinearLayout hero = card("");
    hero.setBackground(rounded(BLUE, 0, 16));
    text(hero, "YOUR CALLING WORKSPACE", 13, true, 0xffdcebdc);
    uploadHeading = text(hero, "", 21, true, Color.WHITE);
    uploadHeading.setId(R.id.upload_heading);
    status = text(hero, "", 15, false, 0xffe2ede1);
    status.setId(R.id.sync_status);
    LinearLayout stats = new LinearLayout(this);
    LinearLayout customerStat = new LinearLayout(this);
    customerStat.setOrientation(LinearLayout.VERTICAL);
    customerCount = text(customerStat, "0", 25, true, Color.WHITE);
    text(customerStat, "Assigned leads", 14, false, 0xffe2ede1);
    LinearLayout waitingStat = new LinearLayout(this);
    waitingStat.setOrientation(LinearLayout.VERTICAL);
    todayCount = text(waitingStat, "0", 25, true, Color.WHITE);
    todayCount.setId(R.id.today_count);
    text(waitingStat, "Calls today", 14, false, 0xffe2ede1);
    stats.addView(customerStat, new LinearLayout.LayoutParams(0, -2, 1));
    stats.addView(waitingStat, new LinearLayout.LayoutParams(0, -2, 1));
    hero.addView(stats);
    summary = text(hero, "", 14, false, 0xffe2ede1);
    if (app().enabled() && callAccess()) {
      Button send = button(hero, "Send updates", false, this::sendUpdates);
      send.setBackground(rounded(0xffe7eedc, 0, 12));
      send.setId(R.id.sync_now);
    }
    if ((!app().enabled() && app().store.meta("enabled_since").isEmpty())
        || (app().enabled() && !recordingFolderReady()
            && !"true".equals(app().store.meta("recording_setup_skipped")))) {
      summary.setVisibility(View.GONE);
    }

    if (!app().enabled()) {
      boolean first = app().store.meta("enabled_since").isEmpty();
      LinearLayout setup = card(first ? "Step 1 of 2 · Allow call access" : "Resume your uploads");
      text(setup, first
          ? "Aven saves calls with customers assigned to you. Allow Phone and Call logs to get started."
          : "Calls already waiting on this phone are kept. Resume to send updates again.",
          16, false, MUTED);
      if (first) {
        consent = new CheckBox(this);
        consent.setText("My company allows me to save customer calls and recordings.");
        consent.setTextColor(INK);
        consent.setTextSize(15);
        consent.setMinHeight(dp(48));
        consent.setId(R.id.sync_consent);
        setup.addView(consent);
      }
      button(setup, first ? "Allow & continue" : "Resume uploads", true, () -> {
        if (consent != null && !consent.isChecked()) {
          notice("Please confirm your company's permission before continuing.");
          return;
        }
        if (app().store.meta("calling_code").isEmpty()) app().store.meta("calling_code", "91");
        requestCallPermissions();
      }).setId(R.id.enable_sync);
      button(setup, "Can't allow permissions?", false, this::permissionHelp);
      if (first)
        text(root, "Recordings are added in the next step. Your Phone app creates the audio.",
            14, false, MUTED);
      else recent = card("Recent calls");
      return;
    }

    if (!callAccess()) {
      LinearLayout access = card("Phone access needs attention");
      text(access, "Allow Phone and Call logs so new customer calls can be saved.", 16, false, MUTED);
      button(access, "Allow phone access", true, this::requestCallPermissions);
      button(access, "Open phone permissions", false, this::openAppSettings);
    } else if (!recordingFolderReady()
        && !"true".equals(app().store.meta("recording_setup_skipped"))) {
      LinearLayout recording = card("Step 2 of 2 · Add call recordings");
      text(recording, "First, turn on call recording in your Phone app. Then choose the folder where it saves the audio.",
          16, false, MUTED);
      button(recording, "Choose recording folder", true, this::chooseFolder).setId(R.id.connect_folder);
      button(recording, "Help me find it", false, this::recordingHelp);
      button(recording, "Set up recordings later", false, () -> {
        app().store.meta("recording_setup_skipped", "true");
        render();
      }).setId(R.id.skip_recordings);
      text(recording, "Call details can be saved while recording setup is unfinished.", 14, false, MUTED);
    }

    LinearLayout work = card("Quick actions");
    button(work, "Open my leads", true, () -> { page = "customers"; render(); });
    button(work, "Browse properties", false, this::openProperties).setId(R.id.property_catalogue);
    LinearLayout recordingState = card("Recordings");
    folderStatus = text(recordingState, "", 15, true, INK);
    folderStatus.setId(R.id.recording_status);
    text(recordingState, recordingFolderReady()
        ? "Audio uploads after your Phone app saves it and Aven matches it to a customer call."
        : "Your call details can upload. Audio needs a recording folder first.", 14, false, MUTED);
    if (!recordingFolderReady())
      button(recordingState, "Set up recordings", false, this::chooseFolder);
    recent = card("Latest conversations");
    button(root, "View all recent calls", false, () -> { page = "calls"; render(); });
    button(root, "How to test a call", false, this::testHelp);
  }

  private void customersScreen() {
    text(root, "Your property leads", 24, true, INK);
    text(root, "The enquiries assigned to you by your company.", 15, false, MUTED);
    status = text(root, "", 14, false, MUTED);
    status.setId(R.id.sync_status);
    EditText search = input(root, "Find a lead", InputType.TYPE_CLASS_TEXT,
        customerQuery, R.id.customer_search);
    search.setHint("Name or phone number");
    search.addTextChangedListener(new TextWatcher() {
      public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
      public void onTextChanged(CharSequence s, int start, int before, int count) {
        customerQuery = s.toString();
        listFingerprint = "";
        refreshDashboard();
      }
      public void afterTextChanged(Editable value) {}
    });
    leadStatus = text(root, "", 14, false, MUTED);
    leadStatus.setId(R.id.lead_status);
    refreshLeadsButton = button(root, "Refresh leads", false, () -> refreshLeads(true));
    refreshLeadsButton.setId(R.id.refresh_leads);
    contacts = card("Assigned to you");
    contacts.setId(R.id.lead_list);
  }

  private void refreshLeads(boolean force) {
    if (!app().session.authenticated() || leadsLoading || isFinishing() || isDestroyed()) return;
    if (!force) {
      if (SystemClock.elapsedRealtime() - leadsAttemptAt < 30_000 && leadsAttemptAt != 0) return;
      try {
        long age = System.currentTimeMillis() - Long.parseLong(app().store.meta("contacts_at"));
        if (age >= 0 && age < 60_000) return;
      } catch (NumberFormatException ignored) { }
    }
    leadsLoading = true;
    leadsAttemptAt = SystemClock.elapsedRealtime();
    leadsError = "";
    refreshDashboard();
    executor.submit(() -> {
      String error = "";
      try { LeadDirectory.refresh(app()); }
      catch (Exception failure) {
        error = failure instanceof Api.Failure ? failure.getMessage()
            : "Couldn't load leads. Check your connection and tap Refresh leads.";
      }
      String message = error;
      main.post(() -> {
        leadsLoading = false;
        leadsError = message;
        listFingerprint = "";
        if (!isFinishing() && !isDestroyed()) {
          if (app().session.authenticated() != renderedAuthenticated) render();
          else refreshDashboard();
        }
      });
    });
  }

  private void openProperties() {
    startActivity(new Intent(this, PropertyActivity.class));
  }

  private void callsScreen() {
    text(root, "Calls & recordings", 24, true, INK);
    text(root, "Your latest 30 calls on this phone. Open a lead’s View history for earlier calls and recordings saved in the CRM.", 15, false, MUTED);
    status = text(root, "", 15, false, MUTED);
    status.setId(R.id.sync_status);
    button(root, app().enabled() ? "Send updates" : "Resume uploads", true, () -> {
      if (app().enabled()) sendUpdates(); else { page = "home"; render(); }
    }).setId(R.id.sync_now);
    LinearLayout filters = new LinearLayout(this);
    filters.setOrientation(getResources().getConfiguration().fontScale > 1.2f
        ? LinearLayout.VERTICAL : LinearLayout.HORIZONTAL);
    root.addView(filters);
    callFilter(filters, "All calls", "all", R.id.calls_all);
    callFilter(filters, "Missed", "missed", R.id.calls_missed);
    callFilter(filters, "Pending audio", "audio", R.id.calls_audio);
    recent = card("Conversations");
    recent.setId(R.id.calls_list);
  }

  private void callFilter(LinearLayout parent, String title, String filter, int id) {
    Button choice = button(parent, (callFilter.equals(filter) ? "✓ " : "") + title,
        false, () -> { callFilter = filter; render(); });
    choice.setId(id);
    choice.setTextSize(14);
    if (parent.getOrientation() == LinearLayout.HORIZONTAL) {
      LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0, -2, 1);
      params.setMargins(dp(2), dp(4), dp(2), dp(6));
      choice.setLayoutParams(params);
    }
    choice.setSelected(callFilter.equals(filter));
    choice.setTextColor(callFilter.equals(filter) ? Color.WHITE : BLUE);
    choice.setBackground(rounded(callFilter.equals(filter) ? BLUE : SOFT, LINE, 10));
    choice.setContentDescription(title + (callFilter.equals(filter) ? ", selected" : ""));
  }

  private void settingsScreen() {
    text(root, "Your workspace", 24, true, INK);
    text(root, "Your account, recordings and upload preferences.", 15, false, MUTED);
    status = text(root, "", 14, false, MUTED);
    status.setId(R.id.sync_status);
    LinearLayout account = card("Your account");
    text(account, app().session.get("name"), 18, true, INK);
    text(account, app().session.get("org_name"), 15, false, MUTED);
    button(account, "Browse properties", false, this::openProperties).setId(R.id.property_catalogue);
    LinearLayout uploads = card("Call uploads");
    text(uploads, app().enabled() ? "Customer call uploads are on." : "Customer call uploads are paused.",
        16, true, INK);
    text(uploads, "Only calls with your assigned customers are sent to the CRM.", 14, false, MUTED);
    if (app().enabled())
      button(uploads, "Pause uploads", false, () -> {
        app().store.meta("enabled", "false");
        SyncScheduler.cancel(this);
        app().api.cancelActive();
        stopService(new Intent(this, SyncService.class));
        page = "home";
        render();
      }).setId(R.id.pause_sync);
    else button(uploads, "Resume uploads", true, () -> { page = "home"; render(); });
    button(uploads, "Phone permissions & battery", false, this::permissionHelp);
    button(uploads, "Country code: +" + callingCodeValue(), false, this::editCallingCode);

    LinearLayout recording = card("Call recordings");
    folderStatus = text(recording, "", 15, true, INK);
    folderStatus.setId(R.id.recording_status);
    text(recording, "Your Phone app records the call. Aven uploads the saved audio. Keep automatic recording on in your Phone app.",
        15, false, MUTED);
    button(recording, recordingFolderReady() ? "Change recording folder" : "Choose recording folder",
        !recordingFolderReady(), this::chooseFolder).setId(R.id.connect_folder);
    button(recording, "Help with recordings", false, this::recordingHelp);
    text(recording, "Supported audio: M4A, MP3, WAV, OGG and FLAC. Maximum file size: "
        + (SyncEngine.recordingLimit(app()) / 1024 / 1024) + " MB.", 14, false, MUTED);

    LinearLayout connection = card("Workspace connection");
    text(connection, "Managed by your company", 16, true, INK);
    TextView address = text(connection, app().session.get("server"), 14, false, MUTED);
    address.setTextIsSelectable(true);
    button(connection, "How to test a call", false, this::testHelp);
    button(account, "Sign out", false, () ->
        new AlertDialog.Builder(this)
            .setTitle("Sign out of this phone?")
            .setMessage("Calls still waiting on this phone will be removed. Calls already saved in the CRM are kept.")
            .setPositiveButton("Sign out", (dialog, which) -> signOut())
            .setNegativeButton("Cancel", null).show()).setId(R.id.sign_out);
    text(root, "Aven Realty · " + BuildConfig.VERSION_NAME, 14, false, MUTED);
  }

  private String callingCodeValue() {
    String value = app().store.meta("calling_code");
    return value.isEmpty() ? "91" : value;
  }

  private void editCallingCode() {
    LinearLayout content = new LinearLayout(this);
    content.setOrientation(LinearLayout.VERTICAL);
    content.setPadding(dp(24), dp(8), dp(24), 0);
    EditText value = input(content, "Country calling code", InputType.TYPE_CLASS_NUMBER,
        callingCodeValue(), R.id.calling_code);
    AlertDialog dialog = new AlertDialog.Builder(this).setTitle("Phone number settings")
        .setView(content).setPositiveButton("Save", null).setNegativeButton("Cancel", null).create();
    dialog.setOnShowListener(ignored -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
      String country = value.getText().toString().trim();
      if (!country.matches("[1-9][0-9]{0,2}")) { value.setError("Enter 1 to 3 digits, such as 91."); return; }
      app().store.meta("calling_code", country);
      dialog.dismiss();
      render();
    }));
    dialog.show();
  }

  private void sendUpdates() {
    if (!callAccess()) { requestCallPermissions(); return; }
    try {
      startForegroundService(new Intent(this, SyncService.class));
      notice("Sending your latest customer calls…");
      noticeUntil = System.currentTimeMillis() + 2000;
    } catch (RuntimeException e) {
      SyncScheduler.upload(this);
      notice("Updates are waiting. Android will send them when it allows background work.");
    }
  }

  private void chooseFolder() {
    try {
      Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
      intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
      startActivityForResult(intent, FOLDER);
    } catch (ActivityNotFoundException error) {
      notice("No folder picker is available. Ask your manager to check this phone's Files app.");
    }
  }

  private void openAppSettings() {
    startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
        Uri.parse("package:" + getPackageName())));
  }

  private void permissionHelp() {
    new AlertDialog.Builder(this).setTitle("Allow Aven to work in the background")
        .setMessage("1. Allow Phone and Call logs.\n\n2. Allow notifications to see upload progress.\n\n3. In your phone's battery settings, allow background activity for Aven Realty.\n\nBattery saving can delay uploads. After a force-stop, open Aven again to resume.")
        .setPositiveButton("Open app settings", (d,w) -> openAppSettings())
        .setNegativeButton("Close", null).show();
  }

  private void recordingHelp() {
    new AlertDialog.Builder(this).setTitle("Connect your call recordings")
        .setMessage("1. Open your usual Phone app and turn on call recording.\n\n2. Make a short test call, then find the saved audio in your Files app.\n\n3. Return to Aven, choose that folder and tap Use this folder.\n\nAven does not record calls itself. If your phone keeps audio private, automatic upload may not be available. You can add an accessible audio file to a call manually.")
        .setPositiveButton("Open Phone app", (d,w) -> {
          try { startActivity(new Intent(Intent.ACTION_DIAL)); }
          catch (ActivityNotFoundException e) { notice("No Phone app is available on this device."); }
        }).setNegativeButton("Close", null).show();
  }

  private void testHelp() {
    new AlertDialog.Builder(this).setTitle("Try your first customer call")
        .setMessage("1. Ask your manager to assign a test customer's phone number to you in the CRM.\n\n2. Turn on recording in your Phone app and connect its recording folder in Aven.\n\n3. Call that customer, talk briefly, then hang up.\n\n4. Tap Send updates. Open Calls to see separate results for call details and the recording. Check playback in the web CRM.")
        .setPositiveButton("Got it", null).show();
  }

  private void requestCallPermissions() {
    ArrayList<String> permissions = new ArrayList<>();
    for (String p :
        new String[] {Manifest.permission.READ_CALL_LOG, Manifest.permission.READ_PHONE_STATE})
      if (checkSelfPermission(p) != PackageManager.PERMISSION_GRANTED) permissions.add(p);
    if (Build.VERSION.SDK_INT >= 33
        && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
            != PackageManager.PERMISSION_GRANTED)
      permissions.add(Manifest.permission.POST_NOTIFICATIONS);
    if (permissions.isEmpty()) enable();
    else requestPermissions(permissions.toArray(new String[0]), PERMISSIONS);
  }

  @Override
  public void onRequestPermissionsResult(int request, String[] permissions, int[] grants) {
    super.onRequestPermissionsResult(request, permissions, grants);
    if (request == PERMISSIONS) {
      if (checkSelfPermission(Manifest.permission.READ_CALL_LOG)
              == PackageManager.PERMISSION_GRANTED
          && checkSelfPermission(Manifest.permission.READ_PHONE_STATE)
              == PackageManager.PERMISSION_GRANTED) enable();
      else
        notice(
            "Allow Phone and Call logs to continue. Tap Can't allow permissions? for help."
                + " If Call logs is blocked, ask your manager to check the installation.");
    }
  }

  private void enable() {
    if (!app().enabled() || app().store.meta("enabled_since").isEmpty())
      app().store.meta("enabled_since", String.valueOf(System.currentTimeMillis()));
    app().store.meta("enabled", "true");
    app().store.meta("status", "Work-call syncing enabled. Preparing your assigned customers…");
    SyncScheduler.restore(this);
    SyncScheduler.capture(this, 0);
    render();
  }

  private void refreshDashboard() {
    if (!app().session.authenticated()) return;
    List<Map<String, String>> calls = recent == null ? List.of()
        : app().store.query("SELECT * FROM calls ORDER BY started DESC,id DESC LIMIT "
            + (page.equals("home") ? "5" : "30"));
    if (page.equals("calls")) calls = calls.stream().filter(call ->
        callFilter.equals("all") || (callFilter.equals("missed") && "missed".equals(call.get("result")))
        || (callFilter.equals("audio") && "answered".equals(call.get("result"))
            && !"uploaded".equals(call.get("recording_state"))
            && !Set.of("excluded", "ambiguous", "error").contains(call.get("state"))))
        .collect(java.util.stream.Collectors.toList());
    String escaped = customerQuery.trim().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_");
    List<Map<String, String>> clients = contacts == null ? List.of()
        : app().store.query("SELECT * FROM contacts WHERE name LIKE ? ESCAPE '\\' OR phone LIKE ? ESCAPE '\\' ORDER BY name COLLATE NOCASE,id LIMIT 100",
            "%" + escaped + "%", "%" + escaped + "%");
    long pending = app().store.pendingCount();
    int customers = Integer.parseInt(app().store.query("SELECT count(*) AS total FROM contacts").get(0).get("total"));
    boolean leadsLoaded = !app().store.meta("contacts_at").isEmpty();
    if (customerCount != null) customerCount.setText(leadsLoaded || customers > 0 ? String.valueOf(customers) : "—");
    if (refreshLeadsButton != null) {
      refreshLeadsButton.setEnabled(!leadsLoading);
      refreshLeadsButton.setText(leadsLoading ? "Refreshing leads…" : "Refresh leads");
    }
    if (leadStatus != null) {
      String leadMessage = leadsLoading ? "Checking your latest assignments…"
          : !leadsError.isEmpty() ? leadsError + (customers > 0 ? " Showing saved leads." : "")
          : leadsLoaded ? customers + (customers == 1 ? " lead assigned to you" : " leads assigned to you") : "";
      leadStatus.setText(leadMessage);
      leadStatus.setVisibility(leadMessage.isEmpty() ? View.GONE : View.VISIBLE);
    }
    if (waitingCount != null) waitingCount.setText(String.valueOf(pending));
    if (todayCount != null) {
      Calendar midnight = Calendar.getInstance();
      midnight.set(Calendar.HOUR_OF_DAY, 0); midnight.set(Calendar.MINUTE, 0);
      midnight.set(Calendar.SECOND, 0); midnight.set(Calendar.MILLISECOND, 0);
      long from = midnight.getTimeInMillis(); midnight.add(Calendar.DAY_OF_MONTH, 1);
      todayCount.setText(app().store.query("SELECT count(*) AS total FROM calls WHERE started>=? AND started<?",
          String.valueOf(from), String.valueOf(midnight.getTimeInMillis())).get(0).get("total"));
    }
    String last = app().store.meta("last_sync");
    String raw = app().store.meta("status");
    String heading, detail;
    if (!app().enabled()) {
      boolean first = app().store.meta("enabled_since").isEmpty();
      heading = first ? "Let's set up your phone" : "Uploads are paused";
      detail = first ? "Two short steps, then you can get back to calling."
          : "Your saved calls stay in the CRM. Resume below when you're ready.";
    } else if (!callAccess()) {
      heading = "Allow phone access";
      detail = "New call details cannot be saved until Phone and Call logs are allowed.";
    } else if (SyncService.active.get()) {
      heading = "Sending your updates…";
      detail = "Checking your customer list and sending calls waiting on this phone.";
    } else if (app().store.reviewCount() > 0) {
      heading = "Some calls need your help";
      detail = "Open Calls to see what needs attention.";
    } else if (!raw.isBlank() && !raw.startsWith("Work calls are up to date")
        && !raw.startsWith("Work-call syncing enabled") && !raw.startsWith("Checking assigned customers")
        && !raw.contains("item(s) remain queued")) {
      heading = "Updates need attention";
      detail = raw.contains("Sync interrupted")
          ? "Your calls are safe on this phone. Check your connection, then tap Send updates."
          : raw;
    } else if (pending > 0) {
      heading = pending + (pending == 1 ? " update waiting" : " updates waiting");
      detail = "Calls stay on this phone until they are saved in the CRM.";
    } else if (last.isEmpty()) {
      heading = "Getting your leads ready";
      detail = "Tap Send updates to refresh your assigned leads.";
    } else {
      heading = "Call details are up to date";
      detail = "New customer calls are sent automatically when Android allows background updates.";
    }
    if (uploadHeading != null) uploadHeading.setText(heading);
    if (status != null) {
      boolean showNotice = System.currentTimeMillis() < noticeUntil && !notice.isBlank();
      status.setText(showNotice ? notice : page.equals("home") ? detail : "");
      status.setVisibility(showNotice || page.equals("home") ? View.VISIBLE : View.GONE);
    }
    if (summary != null) summary.setText(last.isEmpty() ? "No updates sent yet"
        : "Last sent " + DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT)
            .format(new Date(Long.parseLong(last))));
    if (folderStatus != null) folderStatus.setText(recordingFolderReady()
        ? "Recording folder connected"
        : app().store.meta("recording_tree").isEmpty() ? "No recording folder selected"
        : "Choose your recording folder again");
    String fingerprint = calls.toString() + clients + customerQuery + customers + callFilter
        + leadsLoading + leadsError + leadsLoaded;
    if (fingerprint.equals(listFingerprint)) return;
    listFingerprint = fingerprint;
    if (recent != null) {
      while (recent.getChildCount() > 1) recent.removeViewAt(1);
      if (calls.isEmpty()) {
        text(recent, page.equals("calls") && !callFilter.equals("all")
            ? callFilter.equals("missed") ? "No missed calls in this list" : "No pending recordings in this list"
            : "Your first lead conversation starts here", 17, true, INK);
        text(recent, page.equals("calls") && !callFilter.equals("all")
            ? "Choose All calls to see your latest conversations."
            : "Call an assigned property lead. Call details and the recording will appear separately.",
            15, false, MUTED);
      }
      for (Map<String, String> call : calls) {
        LinearLayout row = listRow(recent);
        text(row, call.get("name"), 17, true, INK);
        text(row, call.get("phone"), 14, false, MUTED);
        String result = switch (call.get("result")) {
          case "answered" -> "Answered";
          case "missed" -> "Missed";
          case "rejected" -> "Declined";
          default -> "Answer not confirmed";
        };
        text(row, ("incoming".equals(call.get("direction")) ? "Incoming" : "Outgoing")
            + " · " + result + " · " + EstateFormat.duration(call.get("duration")), 14, false, MUTED);
        text(row, DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT)
            .format(new Date(Long.parseLong(call.get("started")))), 14, false, MUTED);
        text(row, "Call details: " + stateLabel(call.get("state")), 15, true,
            "synced".equals(call.get("state")) ? 0xff23774a : INK);
        String audio = "unavailable".equals(call.get("recording_state"))
            ? "No recording expected" : stateLabel(call.get("recording_state"));
        text(row, "Recording: " + audio, 15, false, MUTED);
        if (!call.get("error").isEmpty()) text(row, call.get("error"), 14, false, 0xff944537);
        if (!"uploaded".equals(call.get("recording_state"))
            && "answered".equals(call.get("result"))
            && !Set.of("excluded", "ambiguous", "error").contains(call.get("state"))) {
          if (app().enabled()) {
            Button add = button(row, "Add recording", false, () -> selectRecording(call.get("id")));
            add.setContentDescription("Add recording for " + call.get("name"));
          } else text(row, "Resume uploads to add a recording.", 14, false, MUTED);
        }
      }
    }
    if (contacts != null) {
      while (contacts.getChildCount() > 1) contacts.removeViewAt(1);
      if (clients.isEmpty()) {
        String emptyTitle = !customerQuery.isBlank() && customers > 0 ? "No matching leads"
            : leadsLoading ? "Loading your leads…"
            : !leadsError.isEmpty() ? "Leads couldn't be refreshed"
            : leadsLoaded ? "No leads assigned yet" : "Leads haven't loaded yet";
        text(contacts, emptyTitle, 17, true, INK);
        text(contacts, !customerQuery.isBlank() && customers > 0 ? "Try a different name or phone number."
            : leadsLoading ? "Your assignments will appear here shortly."
            : !leadsError.isEmpty() || !leadsLoaded ? "Tap Refresh leads to try again. Call uploads can stay paused."
            : "Ask your manager to assign property enquiries to you, then tap Refresh leads.", 15, false, MUTED);
      }
      for (Map<String, String> client : clients) {
        LinearLayout row = listRow(contacts);
        text(row, client.get("name"), 17, true, INK);
        text(row, client.get("phone"), 15, false, MUTED);
        row.setFocusable(true);
        row.setContentDescription("View lead " + client.get("name") + ", " + client.get("phone"));
        row.setOnClickListener(view -> leadDetails(client.get("id")));
        Button history = button(row, "View history", false, () -> leadDetails(client.get("id")));
        history.setId(R.id.lead_history);
        history.setContentDescription("View history for " + client.get("name"));
        if ("1".equals(client.get("dnd"))) text(row, "Do not call", 15, true, 0xff944537);
        else {
          Button call = button(row, "Call lead", true, () -> dialLead(client.get("id")));
          call.setContentDescription("Call " + client.get("name"));
        }
      }
      if (clients.size() == 100) text(contacts, "Showing the first 100 matches. Use search to narrow the list.", 14, false, MUTED);
    }
  }

  private LinearLayout listRow(LinearLayout parent) {
    LinearLayout row = new LinearLayout(this);
    row.setOrientation(LinearLayout.VERTICAL);
    row.setPadding(dp(14), dp(14), dp(14), dp(6));
    row.setBackground(rounded(PAPER, LINE, 12));
    LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
    params.topMargin = dp(8);
    parent.addView(row, params);
    return row;
  }

  private void dialLead(String id) {
    var matches = app().store.query("SELECT * FROM contacts WHERE id=?", id);
    if (matches.isEmpty()) { notice("This lead is no longer in your assigned list."); return; }
    if ("1".equals(matches.get(0).get("dnd"))) { notice("This lead is marked Do not call."); return; }
    try { startActivity(new Intent(Intent.ACTION_DIAL, Uri.fromParts("tel", matches.get(0).get("phone"), null))); }
    catch (ActivityNotFoundException e) { notice("No Phone app is available."); }
  }

  private void leadDetails(String id) {
    if (app().store.query("SELECT id FROM contacts WHERE id=?", id).isEmpty()) return;
    hideKeyboard();
    startActivity(new Intent(this, LeadActivity.class).putExtra("lead_id", id));
  }

  private void selectRecording(String key) {
    selectedCall = key;
    Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
    intent.setType("audio/*");
    intent.addCategory(Intent.CATEGORY_OPENABLE);
    intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
    try { startActivityForResult(intent, AUDIO); }
    catch (ActivityNotFoundException e) { notice("No audio picker is available. Check your phone's Files app."); }
  }

  @Override
  protected void onActivityResult(int request, int result, Intent data) {
    super.onActivityResult(request, result, data);
    if (result != RESULT_OK || data == null || data.getData() == null) return;
    Uri uri = data.getData();
    try {
      getContentResolver().takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION);
    } catch (SecurityException e) {
      notice("File access was not granted. Please choose the folder or recording again.");
      return;
    }
    if (request == FOLDER) {
      app().store.meta("recording_tree", uri.toString());
      app().store.meta("recording_setup_skipped", "false");
      app().store.meta("folder_status", "Recording folder selected; checking available files…");
      SyncScheduler.capture(this, 0);
      render();
    }
    if (request == AUDIO && !selectedCall.isEmpty()) {
      String name = "call-recording.m4a";
      try (Cursor cursor =
          getContentResolver()
              .query(uri, new String[] {OpenableColumns.DISPLAY_NAME}, null, null, null)) {
        if (cursor != null && cursor.moveToFirst()) name = cursor.getString(0);
      } catch (Exception ignored) {
      }
      String fileName = name, key = selectedCall;
      new AlertDialog.Builder(this)
          .setTitle("Add this recording to the call?")
          .setMessage(
              "Add "
                  + fileName
                  + " to the call you selected. Only continue if it belongs to that customer"
                  + " call.")
          .setPositiveButton(
              "Upload",
              (dialog, which) ->
                  run(
                      "Preparing your recording…",
                      () -> {
                        SyncEngine.attachSelected(app(), key, uri, fileName);
                        return new JSONObject();
                      },
                      ignored -> refreshDashboard()))
          .setNegativeButton("Cancel", null)
          .show();
      selectedCall = "";
    }
  }

  private interface Job {
    JSONObject execute() throws Exception;
  }

  private interface Done {
    void accept(JSONObject value);
  }

  private void run(String message, Job job, Done done) {
    if (busy) return;
    busy = true;
    notice(message);
    View submit = findViewById(R.id.login_submit);
    if (submit != null) submit.setEnabled(false);
    executor.submit(
        () -> {
          try {
            JSONObject result = job.execute();
            main.post(
                () -> {
                  busy = false;
                  if (!isFinishing() && !isDestroyed()) {
                    View button = findViewById(R.id.login_submit);
                    if (button != null) button.setEnabled(true);
                    noticeUntil = 0;
                    done.accept(result);
                  }
                });
          } catch (Exception error) {
            if (BuildConfig.DEBUG) android.util.Log.w("AvenUi", "Action failed", error);
            main.post(
                () -> {
                  busy = false;
                  if (!isFinishing() && !isDestroyed()) {
                    View button = findViewById(R.id.login_submit);
                    if (button != null) button.setEnabled(true);
                    notice(error instanceof Api.Failure failure
                        ? failure.status == 422 && !renderedAuthenticated
                            ? "Check the account phone number and try again."
                            : failure.getMessage()
                        : "Couldn't connect. Check your internet and workspace address, then try again.");
                  }
                });
          }
        });
  }

  private void signOut() {
    app().store.meta("enabled", "false");
    SyncScheduler.cancel(this);
    app().api.cancelActive();
    stopService(new Intent(this, SyncService.class));
    run(
        "Signing out…",
        () -> {
          SyncEngine.LOCK.lockInterruptibly();
          try {
            try {
              app().api.logout();
            } catch (Exception unavailable) {
              /* Local sign-out must work offline. The server session expires or can be revoked by an administrator. */
            }
            app().resetLocalData();
            app().session.clear();
            return new JSONObject();
          } finally {
            SyncEngine.LOCK.unlock();
          }
        },
        ignored -> { page = "home"; render(); });
  }

  private void goBack() {
    if (app().session.authenticated() && !page.equals("home")) {
      page = "home";
      render();
    } else finish();
  }

  @Override
  public boolean onKeyUp(int keyCode, KeyEvent event) {
    if (Build.VERSION.SDK_INT < 33 && keyCode == KeyEvent.KEYCODE_BACK && !event.isCanceled()) {
      goBack();
      return true;
    }
    return super.onKeyUp(keyCode, event);
  }
}
