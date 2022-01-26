onunload = function() {
    var viewMode = document.getElementById('view-mode');
    self.name = 'viewModeidx' + viewMode.selectedIndex;
}
onload = function() {
    var idx, viewMode = document.getElementById('view-mode');
    viewMode.selectedIndex = (idx = self.name.split('viewModeidx')) ? idx[1] : 0;
}