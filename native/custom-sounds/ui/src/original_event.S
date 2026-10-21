.text
.global csnd_original_event
csnd_original_event:
stp x29,x30,[sp,#-64]!
b csnd_original_event_body
