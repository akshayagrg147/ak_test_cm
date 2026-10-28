# Synthetic media fixtures

These files contain generated silence or a black video frame, with no customer audio.
Tests read the checked-in bytes; FFmpeg is not a test/runtime dependency.

Regenerate them with:

```sh
python generate.py
```

The audio fixture reproduces the `3gp4` ISO media container brand found in a rejected
native phone `.m4a` upload. The native-metadata variant also has an unversioned
QuickTime metadata box before its audio track, reproducing the dialer's layout
without any customer data. The video fixture verifies that a recognized container
header alone does not qualify a file as an audio recording.
