function getSize() {
    var footerHeight = 62;
    var heightOffset = 0;
    var w = document.documentElement.clientWidth;
    var h = document.documentElement.clientHeight;

    var logo = document.getElementById('logo');
    var logoWidth = logo.clientWidth;
    var titleWidth = document.getElementById('title').clientWidth;
    var logoLeftMarg = parseInt(window.getComputedStyle(document.getElementById('title')).marginLeft);
    var headerHeight = document.getElementById('header').clientHeight;
    var tmp = headerHeight + "px";
    var content = document.getElementById('content');
    content.style.paddingTop = tmp;
    heightOffset = headerHeight + 2 + footerHeight;
    tmp = "calc(100vh - " + heightOffset + "px)";
    content.style.minHeight = tmp;

    if(w < (logoWidth + titleWidth) || (logoLeftMarg <= logoWidth)){
        adjustMobile();
    }else if ((logoLeftMarg > logoWidth) && (logoWidth != 0 ) || (logoLeftMarg > 280)){
        adjustDesktop();
    }
}

function adjustMobile(){
    icon = document.getElementById('logo')
    icon.style.display = 'none';
}

function adjustDesktop(){
    icon = document.getElementById('logo')
    icon.style.display = 'block';
}