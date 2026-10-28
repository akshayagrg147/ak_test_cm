package com.aven.calls;

import android.app.*;
import android.content.*;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.*;
import android.text.InputType;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.*;
import android.view.inputmethod.EditorInfo;
import android.widget.*;
import java.net.URLEncoder;
import java.util.concurrent.*;
import org.json.*;

/** Read-only company inventory using existing CRM APIs; no call-sync state is changed here. */
public class PropertyActivity extends Activity {
  private static final int INK = 0xff193c33, MUTED = 0xff59665f, GREEN = 0xff20594b;
  private static final int PAPER = 0xfff6f6f1, LINE = 0xffdfe5dd;
  private static final String[] TYPES = {"", "apartment", "villa", "plot", "office", "retail", "warehouse", "other"};
  private final ExecutorService network = Executors.newSingleThreadExecutor();
  private final Handler sessionWatch = new Handler(Looper.getMainLooper());
  private final Runnable checkSession = new Runnable() {
    public void run() {
      if (!app().session.authenticated() || !owner.equals(identity())) finish();
      else sessionWatch.postDelayed(this, 3000);
    }
  };
  private LinearLayout root;
  private EditText search;
  private String query = "", draft = "", type = "", listing = "", selected = "", error = "", owner;
  private int page = 1, total, generation;
  private boolean loading;
  private JSONArray items = new JSONArray();
  private JSONObject detail;

  private AvenApplication app() { return AvenApplication.get(); }
  private String identity() { return app().session.get("user_id") + ":" + app().session.get("org_id") + ":" + app().session.get("server"); }
  private int dp(float n) { return Math.round(n * getResources().getDisplayMetrics().density); }

  @Override public void onCreate(Bundle state) {
    super.onCreate(state);
    owner = identity();
    if (state != null) {
      query = state.getString("query", ""); type = state.getString("type", "");
      draft = state.getString("draft", query);
      listing = state.getString("listing", ""); selected = state.getString("selected", "");
      page = state.getInt("page", 1);
    }
    if (Build.VERSION.SDK_INT >= 33)
      getOnBackInvokedDispatcher().registerOnBackInvokedCallback(
          android.window.OnBackInvokedDispatcher.PRIORITY_DEFAULT, this::back);
    fetch();
  }

  @Override protected void onResume() {
    super.onResume();
    sessionWatch.removeCallbacks(checkSession);
    sessionWatch.post(checkSession);
  }

  @Override protected void onPause() {
    sessionWatch.removeCallbacks(checkSession);
    super.onPause();
  }

  @Override protected void onSaveInstanceState(Bundle state) {
    state.putString("query", query);
    state.putString("draft", draft);
    state.putString("type", type); state.putString("listing", listing);
    state.putString("selected", selected); state.putInt("page", page);
    super.onSaveInstanceState(state);
  }

  @Override protected void onDestroy() {
    generation++;
    sessionWatch.removeCallbacksAndMessages(null);
    network.shutdownNow();
    super.onDestroy();
  }

  private GradientDrawable shape(int color) {
    GradientDrawable result = new GradientDrawable();
    result.setColor(color); result.setCornerRadius(dp(16)); result.setStroke(dp(1), LINE);
    return result;
  }

  private TextView text(LinearLayout box, String value, int size, boolean bold, int color) {
    TextView label = new TextView(this);
    label.setText(value); label.setTextSize(size); label.setTextColor(color);
    label.setLineSpacing(dp(3), 1);
    if (bold) label.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
    LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
    params.bottomMargin = dp(9); box.addView(label, params);
    return label;
  }

  private Button button(LinearLayout box, String label, int id, boolean primary, Runnable action) {
    Button button = new Button(this);
    button.setId(id); button.setText(label); button.setTextSize(15); button.setAllCaps(false);
    button.setStateListAnimator(null);
    button.setMinHeight(dp(48)); button.setPadding(dp(12), dp(8), dp(12), dp(8));
    button.setTextColor(primary ? Color.WHITE : GREEN);
    button.setBackground(shape(primary ? GREEN : 0xffeaf1e9));
    LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
    params.topMargin = dp(4); params.bottomMargin = dp(8); box.addView(button, params);
    button.setOnClickListener(v -> action.run()); return button;
  }

  private LinearLayout card() {
    LinearLayout box = new LinearLayout(this); box.setOrientation(LinearLayout.VERTICAL);
    box.setPadding(dp(18), dp(18), dp(18), dp(12)); box.setBackground(shape(Color.WHITE));
    LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
    params.bottomMargin = dp(14); root.addView(box, params); return box;
  }

  private void render() {
    boolean keepFocus = search != null && search.hasFocus() && !loading;
    int selection = search == null ? 0 : search.getSelectionStart();
    search = null;
    LinearLayout shell = new LinearLayout(this); shell.setOrientation(LinearLayout.VERTICAL);
    shell.setBackgroundColor(PAPER);
    LinearLayout header = new LinearLayout(this); header.setPadding(dp(20), dp(8), dp(20), 0);
    shell.addView(header);
    Button backButton = button(header, selected.isEmpty() ? "‹  Back to workspace" : "‹  Back to properties",
        R.id.property_back, false, this::back);
    backButton.setBackgroundColor(Color.TRANSPARENT); backButton.setGravity(Gravity.START | Gravity.CENTER_VERTICAL);
    ScrollView scroll = new ScrollView(this); scroll.setFillViewport(true);
    root = new LinearLayout(this); root.setOrientation(LinearLayout.VERTICAL);
    root.setPadding(dp(20), dp(12), dp(20), dp(24)); root.setId(R.id.property_results);
    scroll.addView(root); shell.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
    text(root, selected.isEmpty() ? "Property catalogue" : "Property details", 24, true, INK);
    if (selected.isEmpty()) {
      text(root, "Your company's inventory, ready for the next conversation.", 15, false, MUTED);
      LinearLayout filters = card();
      TextView caption = text(filters, "Search your inventory", 14, true, INK);
      caption.setLabelFor(R.id.property_search);
      search = new EditText(this); search.setId(R.id.property_search);
      search.setText(draft); search.setTextSize(16); search.setTextColor(INK);
      search.addTextChangedListener(new TextWatcher() {
        public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
        public void onTextChanged(CharSequence s, int start, int before, int count) { draft = s.toString(); }
        public void afterTextChanged(Editable value) {}
      });
      search.setHintTextColor(MUTED); search.setHint("Project, area or property reference");
      search.setSingleLine(true); search.setInputType(InputType.TYPE_CLASS_TEXT);
      search.setContentDescription("Search properties");
      search.setImeOptions(EditorInfo.IME_ACTION_SEARCH);
      search.setPadding(dp(12), dp(10), dp(12), dp(10)); search.setMinHeight(dp(48));
      search.setBackground(shape(PAPER)); filters.addView(search, new LinearLayout.LayoutParams(-1, -2));
      button(filters, "Search properties", R.id.property_submit, true, this::submit);
      search.setOnEditorActionListener((v, action, event) -> {
        if (action == EditorInfo.IME_ACTION_SEARCH) { submit(); return true; } return false;
      });
      LinearLayout choices = new LinearLayout(this);
      boolean stacked = getResources().getConfiguration().fontScale > 1.2f;
      choices.setOrientation(stacked ? LinearLayout.VERTICAL : LinearLayout.HORIZONTAL);
      filters.addView(choices);
      Button types = button(choices, type.isEmpty() ? "All types" : EstateFormat.label(type),
          R.id.property_type, false, this::chooseType);
      Button listings = button(choices, listing.isEmpty() ? "Sale & rent" : listing.equals("sale") ? "For sale" : "For rent",
          R.id.property_listing, false, this::chooseListing);
      types.setContentDescription("Property type: " + (type.isEmpty() ? "All types" : type));
      listings.setContentDescription("Listing type: " + (listing.isEmpty() ? "Sale and rent" : listing));
      if (!stacked) for (Button option : new Button[] {types, listings}) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0, -2, 1);
        params.setMargins(dp(2), dp(4), dp(2), dp(8)); option.setLayoutParams(params);
      }
    }
    if (loading) {
      LinearLayout box = card();
      ProgressBar progress = new ProgressBar(this); box.addView(progress, new LinearLayout.LayoutParams(dp(30), dp(30)));
      text(box, "Loading properties…", 16, true, INK);
    } else if (!error.isEmpty()) {
      LinearLayout box = card(); text(box, "Properties couldn't be loaded", 18, true, INK);
      text(box, error, 15, false, MUTED);
      button(box, "Try again", R.id.property_retry, true, this::fetch);
    } else if (!selected.isEmpty() && detail != null) renderDetail(detail);
    else {
      text(root, total + (total == 1 ? " property" : " properties") + " · Page " + page, 14, true, MUTED);
      if (items.length() == 0) {
        LinearLayout box = card(); text(box, "No properties found", 19, true, INK);
        text(box, query.isBlank() && type.isEmpty() && listing.isEmpty()
            ? "Your company hasn't added any properties yet. Ask your manager to add inventory in the CRM."
            : "Try another area, project or property type.", 15, false, MUTED);
        if (!query.isBlank() || !type.isEmpty() || !listing.isEmpty())
          button(box, "Clear search & filters", R.id.property_refresh, false, () -> {
            draft = query = type = listing = ""; page = 1; fetch();
          });
      }
      for (int i = 0; i < items.length(); i++) {
        JSONObject property = items.optJSONObject(i); if (property != null) renderCard(property);
      }
      if (page > 1) button(root, "Previous page", R.id.property_previous, false, () -> { page--; fetch(); });
      if ((long) page * 24 < total) button(root, "Next page", R.id.property_next, true, () -> { page++; fetch(); });
    }
    setContentView(shell);
    if (keepFocus && search != null) {
      search.requestFocus();
      search.setSelection(Math.max(0, Math.min(selection, search.length())));
    }
    shell.setOnApplyWindowInsetsListener((view, insets) -> {
      shell.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
          insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom()); return insets;
    }); shell.requestApplyInsets();
  }

  private void renderCard(JSONObject p) {
    LinearLayout box = card();
    LinearLayout meta = new LinearLayout(this); meta.setGravity(Gravity.CENTER_VERTICAL);
    ImageView icon = new ImageView(this); icon.setImageResource(R.drawable.ic_property);
    icon.setPadding(dp(8), dp(8), dp(8), dp(8)); icon.setBackground(shape(0xffeaf1e9));
    icon.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
    meta.addView(icon, new LinearLayout.LayoutParams(dp(42), dp(42)));
    LinearLayout caption = new LinearLayout(this); caption.setOrientation(LinearLayout.VERTICAL);
    caption.setPadding(dp(12), dp(4), 0, 0); meta.addView(caption, new LinearLayout.LayoutParams(0, -2, 1));
    text(caption, EstateFormat.label(p.optString("property_type")) + " · "
        + ("rent".equals(p.optString("listing_type")) ? "For rent" : "For sale"), 14, true, GREEN);
    text(caption, EstateFormat.label(p.optString("status")), 14, false, MUTED);
    LinearLayout.LayoutParams metaParams = new LinearLayout.LayoutParams(-1, -2); metaParams.bottomMargin = dp(10);
    box.addView(meta, metaParams);
    text(box, p.optString("title"), 20, true, INK);
    text(box, location(p), 15, false, MUTED);
    text(box, EstateFormat.money(p.optString("price"), "rent".equals(p.optString("listing_type"))), 22, true, INK);
    text(box, EstateFormat.area(p.optString("area_sqft")) + roomSummary(p), 14, false, MUTED);
    button(box, "View property", View.generateViewId(), false, () -> {
      selected = p.optString("id"); fetch();
    }).setContentDescription("View property " + p.optString("title"));
  }

  private String location(JSONObject p) {
    String area = p.optString("locality"), city = p.optString("city");
    return area.isBlank() ? city : city.isBlank() ? area : area + ", " + city;
  }

  private String roomSummary(JSONObject p) {
    if (p.isNull("bedrooms") || !java.util.Set.of("apartment", "villa").contains(p.optString("property_type"))) return "";
    return " · " + (p.optInt("bedrooms") == 0 ? "Studio" : p.optInt("bedrooms") + " bedrooms");
  }

  private void fact(LinearLayout box, String label, JSONObject p, String key) {
    if (p.isNull(key) || p.optString(key).isBlank()) return;
    text(box, label, 14, false, MUTED); text(box, p.optString(key), 16, true, INK);
  }

  private void renderDetail(JSONObject p) {
    LinearLayout hero = card();
    text(hero, EstateFormat.label(p.optString("property_type")) + " · " + EstateFormat.label(p.optString("status")), 14, true, GREEN);
    text(hero, p.optString("title"), 24, true, INK);
    text(hero, location(p), 16, false, MUTED);
    text(hero, EstateFormat.money(p.optString("price"), "rent".equals(p.optString("listing_type"))), 24, true, GREEN);
    text(hero, "Listed price: " + EstateFormat.exactMoney(p.optString("price")) + ("rent".equals(p.optString("listing_type")) ? " per month" : ""), 14, false, MUTED);
    text(hero, EstateFormat.area(p.optString("area_sqft")) + roomSummary(p), 16, true, INK);
    LinearLayout info = card(); text(info, "Property information", 18, true, INK);
    fact(info, "Reference", p, "reference"); fact(info, "Project", p, "project");
    fact(info, "Developer", p, "developer"); fact(info, "Address", p, "address");
    String propertyType = p.optString("property_type");
    if (java.util.Set.of("apartment", "villa").contains(propertyType)) fact(info, "Bedrooms", p, "bedrooms");
    if (!propertyType.equals("plot")) fact(info, "Bathrooms", p, "bathrooms");
    fact(info, "Possession", p, "possession"); fact(info, "RERA number", p, "rera_number");
    if (!p.optString("description").isBlank()) {
      LinearLayout about = card(); text(about, "About this property", 18, true, INK);
      text(about, p.optString("description"), 16, false, MUTED);
    }
    JSONArray amenities = p.optJSONArray("amenities");
    if (amenities != null && amenities.length() > 0) {
      LinearLayout box = card(); text(box, "Amenities", 18, true, INK);
      for (int i = 0; i < amenities.length(); i++) text(box, "• " + amenities.optString(i), 15, false, MUTED);
    }
    button(root, "Refresh property", R.id.property_refresh, false, this::fetch);
  }

  private void submit() {
    query = draft.trim(); draft = query; page = 1;
    android.view.inputmethod.InputMethodManager keyboard = (android.view.inputmethod.InputMethodManager)getSystemService(INPUT_METHOD_SERVICE);
    if (keyboard != null) keyboard.hideSoftInputFromWindow(search.getWindowToken(), 0);
    fetch();
  }

  private void chooseType() {
    String[] labels = new String[TYPES.length]; labels[0] = "All property types";
    for (int i = 1; i < labels.length; i++) labels[i] = EstateFormat.label(TYPES[i]);
    new AlertDialog.Builder(this).setTitle("Property type").setItems(labels, (dialog, which) -> {
      query = search.getText().toString().trim(); type = TYPES[which]; page = 1; fetch();
    }).setNegativeButton("Cancel", null).show();
  }

  private void chooseListing() {
    new AlertDialog.Builder(this).setTitle("Listing type")
        .setItems(new String[] {"For sale & rent", "For sale", "For rent"}, (dialog, which) -> {
          query = search.getText().toString().trim(); listing = new String[] {"", "sale", "rent"}[which]; page = 1; fetch();
        }).setNegativeButton("Cancel", null).show();
  }

  private void fetch() {
    if (!app().session.authenticated() || !owner.equals(identity())) { finish(); return; }
    int request = ++generation; loading = true; error = ""; detail = null; items = new JSONArray(); render();
    final String path;
    try {
      path = selected.isEmpty() ? "/properties?page=" + page + "&q=" + URLEncoder.encode(query, "UTF-8")
          + "&property_type=" + type + "&listing_type=" + listing : "/properties/" + URLEncoder.encode(selected, "UTF-8");
    } catch (java.io.UnsupportedEncodingException impossible) { throw new IllegalStateException(impossible); }
    final boolean single = !selected.isEmpty();
    network.submit(() -> {
      try {
        JSONObject response = app().api.json("GET", path, null);
        runOnUiThread(() -> {
          if (request != generation || isFinishing() || isDestroyed()) return;
          if (!app().session.authenticated() || !owner.equals(identity())) { finish(); return; }
          loading = false;
          if (single) detail = response;
          else { items = response.optJSONArray("items"); if (items == null) items = new JSONArray(); total = response.optInt("total"); }
          render();
        });
      } catch (Exception failure) {
        runOnUiThread(() -> {
          if (request != generation || isFinishing() || isDestroyed()) return;
          if (!app().session.authenticated() || !owner.equals(identity())) { finish(); return; }
          loading = false;
          error = failure instanceof Api.Failure f && (f.status == 403 || f.status == 404)
              ? "This property or catalogue is no longer available to your account. Return to your workspace or try again."
              : "Check your internet connection and try again. Your saved calls are still on this phone.";
          render();
        });
      }
    });
  }

  private void back() { if (selected.isEmpty()) finish(); else { selected = ""; fetch(); } }

  @Override public boolean onKeyUp(int code, KeyEvent event) {
    if (Build.VERSION.SDK_INT < 33 && code == KeyEvent.KEYCODE_BACK && !event.isCanceled()) { back(); return true; }
    return super.onKeyUp(code, event);
  }
}
